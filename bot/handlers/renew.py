from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func
from bot.database import ConfigProfile, Payment, Admin, Package, User, DiscountCode, get_db, get_setting
from bot.panel_api import panel_api
from bot.config import Config as BotConfig
from bot.auth import is_admin
from bot.handlers.start import PHONE_KB
from bot.utils.helpers import send_config_package
from datetime import datetime
import time

router = Router()

class RenewState(StatesGroup):
    waiting_for_receipt = State()
    waiting_for_discount_code = State()

async def show_renew_card_info(message: Message, amount: int, state: FSMContext):
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
        
    text = f"💳 **پرداخت تمدید:**\n💰 مبلغ اصلی: `{amount:,}` T\n"
    if discount_code and amount >= min_amount:
        discount_value = int(amount * discount_percent / 100)
        text += f"🎟 تخفیف `{discount_code}`: -`{discount_value:,}` T\n✅ **مبلغ نهایی: `{final_amount:,}` T**\n"
    text += f"💳 `{card_num}`\n👤 {card_name or 'نامشخص'}\n📸 عکس رسید را ارسال کنید."
    await message.answer(text, parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ انصراف")]], resize_keyboard=True))
    await state.update_data(amount=final_amount)
    await state.set_state(RenewState.waiting_for_receipt)

@router.message(F.text == "🔄 تمدید")
async def renew_menu(message: Message):
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one_or_none()
        if not user or not user.phone_verified:
            return await message.answer("🔐 برای تمدید سرویس، لطفاً ابتدا شماره تماس خود را تایید کنید.", reply_markup=PHONE_KB)
        result = await session.execute(select(ConfigProfile).where(ConfigProfile.telegram_id == message.from_user.id, ConfigProfile.is_test == False))
        configs = result.scalars().all()
    if not configs:
        return await message.answer("❌ **کانفیگی برای تمدید ندارید.**", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛒 خرید کانفیگ")], [KeyboardButton(text="🔙 بازگشت به منو")]], resize_keyboard=True), parse_mode="Markdown")
    text = "🔄 **قابل تمدید:**\n"
    kb_buttons = []
    for c in configs:
        if c.is_unlimited_time: expiry_display = "♾️"
        else:
            expiry_days = max(0, (c.expiry_time - int(time.time() * 1000)) // (1000 * 86400)) if c.expiry_time else 0
            expiry_display = f"{expiry_days}d"
        vol = "♾️" if c.is_unlimited_volume else f"{c.volume_gb}GB"
        kb_buttons.append([InlineKeyboardButton(text=f"🔗 {c.username} | {vol} | {expiry_display}", callback_data=f"select_renew:{c.id}")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("select_renew:"))
async def select_renew(callback: CallbackQuery, state: FSMContext):
    config_id = int(callback.data.split(":")[1])
    async for session in get_db():
        config = (await session.execute(select(ConfigProfile).where(ConfigProfile.id == config_id))).scalar_one_or_none()
    if not config or config.telegram_id != callback.from_user.id: return await callback.answer("دسترسی ندارید", show_alert=True)
    
    vol = 0 if config.is_unlimited_volume else config.volume_gb
    dur = 0 if config.is_unlimited_time else config.duration_days
    async for session in get_db():
        pkg = (await session.execute(select(Package).where(Package.volume_gb == vol, Package.duration_days == dur, Package.is_active == True).order_by(Package.price.asc()))).scalar_one_or_none()
    if pkg: renew_price, pkg_name_for_display = pkg.price, pkg.name
    else:
        v = config.volume_gb if config.volume_gb > 0 else 10
        d = config.duration_days if config.duration_days > 0 else 30
        renew_price = (v * 5000) + (d * 2000)
        pkg_name_for_display = "بسته سفارشی"
        
    await state.update_data(config_id=config_id, renew_price=renew_price, username=config.username, pkg_name=pkg_name_for_display)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 اعمال کد تخفیف", callback_data="apply_discount_renew")],
        [InlineKeyboardButton(text="➡️ ادامه و پرداخت", callback_data="skip_discount_renew")]
    ])
    await callback.message.edit_text(f"🔄 **تمدید سرویس:** `{config.username}`\n💰 **هزینه تمدید:** `{renew_price:,}` تومان\n\nآیا کد تخفیف دارید؟", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "skip_discount_renew")
async def skip_discount_renew(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await show_renew_card_info(callback.message, data['renew_price'], state)

@router.callback_query(F.data == "apply_discount_renew")
async def apply_discount_renew(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎟 لطفاً کد تخفیف خود را ارسال کنید (یا /cancel):")
    await state.set_state(RenewState.waiting_for_discount_code)

@router.message(RenewState.waiting_for_discount_code)
async def process_discount_code_renew(message: Message, state: FSMContext):
    if message.text == "/cancel":
        data = await state.get_data()
        await show_renew_card_info(message, data['renew_price'], state)
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
            await message.answer("❌ این کد فقط برای **اولین خرید** معتبر است.")
            return
            
        data = await state.get_data()
        amount = data['renew_price']
        if amount < dc.min_amount:
            await message.answer(f"❌ حداقل مبلغ برای این کد `{dc.min_amount:,}` تومان است.")
            return
            
        await state.update_data(discount_code=code, discount_percent=dc.percent, min_amount=dc.min_amount)
        await message.answer(f"✅ کد تخفیف `{dc.percent}%` اعمال شد!")
        await show_renew_card_info(message, amount, state)

@router.message(RenewState.waiting_for_receipt, F.text == "❌ انصراف")
async def cancel_renew(message: Message, state: FSMContext):
    await state.clear()
    from bot.handlers.start import MAIN_MENU
    await message.answer("لغو شد.", reply_markup=MAIN_MENU)

@router.message(RenewState.waiting_for_receipt, F.photo)
async def process_renew_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    config_id = data["config_id"]
    renew_price = data["renew_price"]
    username = data["username"]
    async for session in get_db():
        payment = Payment(telegram_id=message.from_user.id, amount=renew_price, status="pending", package_id=None)
        session.add(payment)
        await session.commit()
        payment_id = payment.id
    await state.clear()
    from bot.handlers.start import MAIN_MENU
    await message.answer(f"✅ تمدید ثبت شد (#{payment_id}).", reply_markup=MAIN_MENU)
    
    forwarded = await message.forward(chat_id=BotConfig.ADMIN_ID)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید", callback_data=f"approve_renew_{payment_id}_{config_id}")],
        [InlineKeyboardButton(text="❌ رد", callback_data=f"reject_pay_{payment_id}")]
    ])
    admin_ids = [BotConfig.ADMIN_ID]
    try:
        async for session in get_db():
            result = await session.execute(select(Admin))
            admin_ids.extend([a.telegram_id for a in result.scalars().all()])
    except: pass
    
    msg_text = f"🔄 **تمدید**\n👤 `{message.from_user.id}`\n🔗 `{username}`\n💰 `{renew_price:,}` T\n🆔 `{payment_id}`"
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, msg_text, reply_to_message_id=forwarded.message_id if admin_id == BotConfig.ADMIN_ID else None, reply_markup=kb, parse_mode="Markdown")
            if admin_id != BotConfig.ADMIN_ID: await bot.forward_message(chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id)
        except: pass

@router.callback_query(F.data.startswith("approve_renew_"))
async def approve_renew(callback: CallbackQuery, bot: Bot):
    if not await is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    payment_id = int(parts[2])
    config_id = int(parts[3])
    async for session in get_db():
        payment = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
        config = (await session.execute(select(ConfigProfile).where(ConfigProfile.id == config_id))).scalar_one_or_none()
    if not payment or payment.status != "pending" or not config: return await callback.answer("نامعتبر", show_alert=True)
    
    async for session in get_db():
        payment.status = "approved"
        await session.commit()
        
    res = await panel_api.renew_client(
        email=config.username,
        total_gb=config.volume_gb if not config.is_unlimited_volume else 0,
        expiry_hours=config.duration_days * 24 if not config.is_unlimited_time else 0,
        server_id=config.server_id,
        unlimited_volume=config.is_unlimited_volume,
        unlimited_time=config.is_unlimited_time
    )
    if res["success"]:
        if res.get("expiry_time_ms"):
            async for session in get_db():
                config.expiry_time = res["expiry_time_ms"]
                await session.commit()
                
        vol_display = "♾️ نامحدود" if config.is_unlimited_volume else f"{config.volume_gb} GB"
        dur_display = "♾️ نامحدود" if config.is_unlimited_time else f"{config.duration_days} روز"
        
        await send_config_package(
            bot=bot, user_id=payment.telegram_id, sub_link=config.sub_link,
            username=config.username, volume_display=vol_display, duration_display=dur_display, is_renew=True
        )
        await callback.message.edit_text(callback.message.text + "\n✅ تمدید شد", parse_mode="Markdown")
    else:
        await callback.message.edit_text(callback.message.text + f"\n⚠️ {res['msg']}", parse_mode="Markdown")
