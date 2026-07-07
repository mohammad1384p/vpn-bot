from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func
from bot.database import Payment, DiscountCode, Admin, get_db, get_setting
from bot.config import Config
from bot.auth import is_admin
from datetime import datetime

router = Router()

class PaymentState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()
    waiting_for_discount_code = State()

async def show_card_info(message: Message, amount: int, state: FSMContext):
    data = await state.get_data()
    discount_code = data.get("discount_code")
    discount_percent = data.get("discount_percent", 0)
    min_amount = data.get("min_amount", 0)
    final_amount = amount
    
    if discount_code and amount >= min_amount:
        discount_value = int(amount * discount_percent / 100)
        final_amount = amount - discount_value
        await state.update_data(discount_amount=discount_value, final_amount=final_amount)
    else:
        await state.update_data(discount_amount=0, final_amount=amount)
        
    async for session in get_db():
        card_num = await get_setting(session, "card_number", "")
        card_name = await get_setting(session, "card_name", "")
    if not card_num:
        await message.answer("❌ شماره کارت تنظیم نشده.")
        await state.clear()
        return
        
    text = f"💳 **پرداخت:**\n💰 مبلغ اصلی: `{amount:,}` T\n"
    if discount_code and amount >= min_amount:
        discount_value = int(amount * discount_percent / 100)
        text += f"🎟 تخفیف `{discount_code}`: -`{discount_value:,}` T\n✅ **مبلغ نهایی: `{final_amount:,}` T**\n"
    text += f"💳 `{card_num}`\n👤 {card_name or 'نامشخص'}\n📸 عکس رسید را ارسال کنید."
    await message.answer(text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    await state.update_data(amount=final_amount)
    await state.set_state(PaymentState.waiting_for_receipt)

@router.message(PaymentState.waiting_for_amount, F.text.isdigit())
async def process_amount(message: Message, state: FSMContext):
    amount = int(message.text)
    if amount < 10000: return await message.answer("❌ حداقل ۱۰,۰۰۰ تومان.")
    await state.update_data(amount=amount, package_name="سفارش اختصاصی")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 اعمال کد تخفیف", callback_data="apply_discount_purchase")],
        [InlineKeyboardButton(text="➡️ ادامه و پرداخت", callback_data="skip_discount_purchase")]
    ])
    await message.answer(f"💰 **مبلغ وارد شده:** `{amount:,}` تومان\n\nآیا کد تخفیف دارید؟", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "skip_discount_purchase")
async def skip_discount_purchase(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await show_card_info(callback.message, data['amount'], state)

@router.callback_query(F.data == "apply_discount_purchase")
async def apply_discount_purchase(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎟 لطفاً کد تخفیف خود را ارسال کنید (یا /cancel):")
    await state.set_state(PaymentState.waiting_for_discount_code)

@router.message(PaymentState.waiting_for_discount_code)
async def process_discount_code_purchase(message: Message, state: FSMContext):
    if message.text == "/cancel":
        data = await state.get_data()
        await show_card_info(message, data['amount'], state)
        return
        
    code = message.text.strip().upper()
    async for session in get_db():
        dc = (await session.execute(select(DiscountCode).where(DiscountCode.code == code))).scalar_one_or_none()
        if not dc or not dc.is_active:
            await message.answer("❌ کد نامعتبر است. لطفاً مجدداً تلاش کنید یا /cancel را بزنید.")
            return
        if dc.expires_at and dc.expires_at < datetime.utcnow():
            await message.answer("❌ کد منقضی شده است.")
            return
        if dc.max_uses > 0 and dc.used_count >= dc.max_uses:
            await message.answer("❌ ظرفیت این کد تمام شده است.")
            return
        if dc.is_first_purchase:
            approved_count = (await session.execute(select(func.count(Payment.id)).where(Payment.telegram_id == message.from_user.id, Payment.status == "approved"))).scalar() or 0
            if approved_count > 0:
                await message.answer("❌ این کد فقط برای **اولین خرید** معتبر است.")
                return
        if dc.is_renewal:
            await message.answer("❌ این کد فقط برای **تمدید** معتبر است.")
            return
            
        data = await state.get_data()
        amount = data['amount']
        if amount < dc.min_amount:
            await message.answer(f"❌ حداقل مبلغ برای این کد `{dc.min_amount:,}` تومان است.")
            return
            
        await state.update_data(discount_code=code, discount_percent=dc.percent, min_amount=dc.min_amount)
        await message.answer(f"✅ کد تخفیف `{dc.percent}%` اعمال شد!")
        await show_card_info(message, amount, state)

@router.message(PaymentState.waiting_for_receipt, F.photo)
async def process_receipt(message: Message, state: FSMContext, bot: Bot):
    photo = message.photo[-1]
    if photo.file_size > 5 * 1024 * 1024: return await message.answer("❌ حجم عکس بالاست.")
    data = await state.get_data()
    amount = data.get("final_amount", data["amount"])
    package_id = data.get("package_id")
    package_name = data.get("package_name", "سفارش اختصاصی")
    discount_code = data.get("discount_code")
    discount_amount = data.get("discount_amount", 0)
    
    async for session in get_db():
        if discount_code:
            dc = (await session.execute(select(DiscountCode).where(DiscountCode.code == discount_code))).scalar_one_or_none()
            if dc: dc.used_count += 1
        new_payment = Payment(
            telegram_id=message.from_user.id, amount=amount, status="pending",
            package_id=package_id, discount_code=discount_code, discount_amount=discount_amount
        )
        session.add(new_payment)
        await session.commit()
        payment_id = new_payment.id
        
    await state.clear()
    from bot.handlers.start import MAIN_MENU
    await message.answer("✅ رسید ثبت شد. در انتظار تایید.", reply_markup=MAIN_MENU)
    
    admin_ids = [Config.ADMIN_ID]
    try:
        async for session in get_db():
            result = await session.execute(select(Admin))
            admin_ids.extend([a.telegram_id for a in result.scalars().all()])
    except: pass
    
    forwarded_msg = await message.forward(chat_id=Config.ADMIN_ID)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید", callback_data=f"approve_pay_{payment_id}")],
        [InlineKeyboardButton(text="❌ رد", callback_data=f"reject_pay_{payment_id}")]
    ])
    pkg_info = f"📦 `{package_name}`" if package_id else "✍️ سفارش اختصاصی"
    discount_info = f"\n🎟 `{discount_code}`: -{discount_amount:,}T" if discount_code else ""
    msg_text = f"🔔 **پرداخت جدید**\n{pkg_info}{discount_info}\n👤 `{message.from_user.id}`\n💰 `{amount:,}` T\n🆔 `{payment_id}`"
    
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                admin_id, msg_text,
                reply_to_message_id=forwarded_msg.message_id if admin_id == Config.ADMIN_ID else None,
                reply_markup=kb, parse_mode="Markdown"
            )
            if admin_id != Config.ADMIN_ID:
                await bot.forward_message(chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id)
        except: pass
