from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from bot.database import Package, User, get_db
from bot.handlers.payment import PaymentState, show_card_info
from bot.handlers.start import PHONE_KB, requires_phone_auth

router = Router()

@router.message(F.text == "🛒 خرید کانفیگ")
async def show_packages(message: Message, state: FSMContext):
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one_or_none()
        if not user:
            await message.answer("⚠️ لطفاً ابتدا /start را بزنید.")
            return
        if requires_phone_auth(user):
            await message.answer("🔐 چون با لینک زیرمجموعه وارد شده‌اید، برای خرید کانفیگ ابتدا شماره تماس خود را تایید کنید.", reply_markup=PHONE_KB)
            return
        result = await session.execute(select(Package).where(Package.is_active == True).order_by(Package.sort_order.asc(), Package.price.asc()))
        packages = result.scalars().all()
    if not packages:
        await message.answer("⚠️ بسته‌ای تعریف نشده. مبلغ دلخواه را وارد کنید:")
        await state.set_state(PaymentState.waiting_for_amount)
        return
    text = "🛒 **بسته‌های موجود:**\n"
    kb_buttons = []
    for pkg in packages:
        vol = "♾️ نامحدود" if pkg.volume_gb <= 0 else f"{pkg.volume_gb}GB"
        dur = "♾️ نامحدود" if pkg.duration_days <= 0 else f"{pkg.duration_days}d"
        label = f"{pkg.name} | 📦 {vol} | ⏱ {dur} | 💰 {pkg.price:,}T"
        kb_buttons.append([InlineKeyboardButton(text=label, callback_data=f"select_pkg:{pkg.id}")])
    kb_buttons.append([InlineKeyboardButton(text="✍️ مبلغ دلخواه", callback_data="custom_amount")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("select_pkg:"))
async def select_package(callback: CallbackQuery, state: FSMContext):
    pkg_id = int(callback.data.split(":")[1])
    async for session in get_db():
        pkg = (await session.execute(select(Package).where(Package.id == pkg_id))).scalar_one_or_none()
    if not pkg: return await callback.answer("یافت نشد", show_alert=True)
    
    await state.update_data(
        amount=pkg.price, package_id=pkg.id, package_name=pkg.name,
        volume_gb=pkg.volume_gb, duration_days=pkg.duration_days
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 اعمال کد تخفیف", callback_data="apply_discount_purchase")],
        [InlineKeyboardButton(text="➡️ ادامه و پرداخت", callback_data="skip_discount_purchase")]
    ])
    await callback.message.edit_text(
        f"📦 **بسته انتخابی:** {pkg.name}\n💰 **قیمت:** `{pkg.price:,}` تومان\n\nآیا کد تخفیف دارید؟",
        reply_markup=kb, parse_mode="Markdown"
    )

@router.callback_query(F.data == "custom_amount")
async def custom_amount(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("✍️ مبلغ دلخواه (تومان):")
    await state.set_state(PaymentState.waiting_for_amount)
