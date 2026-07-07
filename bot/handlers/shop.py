from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from bot.database import User, ConfigProfile, get_db, get_setting
from bot.panel_api import panel_api
from bot.handlers.inbounds import get_selected_inbound_ids
from bot.handlers.payment import PaymentState
from bot.handlers.start import PHONE_KB
from bot.utils.helpers import send_config_package
import time, logging

router = Router()

async def get_bot_username(session, bot: Bot) -> str:
    bot_username_setting = await get_setting(session, "bot_username", "")
    if bot_username_setting: return bot_username_setting
    if bot.me and getattr(bot.me, 'username', None): return bot.me.username
    return 'bot'

@router.message(F.text == "👥 کیف پول")
async def show_wallet(message: Message, bot: Bot):
    try:
        async for session in get_db():
            user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one_or_none()
            if not user or not user.phone_verified:
                await message.answer("🔐 برای مشاهده کیف پول، لطفاً ابتدا شماره تماس خود را تایید کنید.", reply_markup=PHONE_KB)
                return
            refs_count = (await session.execute(select(func.count(User.id)).where(User.referred_by == user.referral_code))).scalar() or 0
            free_threshold = int(await get_setting(session, "free_config_threshold", "50000"))
            referral_reward = int(await get_setting(session, "referral_reward", "10000"))
            bot_username = await get_bot_username(session, bot)
            referral_link = f"https://t.me/{bot_username}?start={user.referral_code}"
            text = (
                f"👛 **کیف پول شما:**\n"
                f"💰 موجودی: `{user.wallet:,}` تومان\n"
                f"👥 زیرمجموعه‌ها: `{refs_count}` نفر\n"
                f"🎁 پاداش هر زیرمجموعه: `{referral_reward:,}` تومان\n"
                f"🎯 آستانه دریافت رایگان: `{free_threshold:,}` تومان\n"
                f"🔗 **لینک دعوت شما:**\n`{referral_link}`"
            )
            kb_buttons = [
                [InlineKeyboardButton(text="💳 افزایش موجودی", callback_data="pay_card")],
                [InlineKeyboardButton(text="📋 کپی لینک دعوت", callback_data="copy_referral_link"),
                 InlineKeyboardButton(text="📤 اشتراک‌گذاری", switch_inline_query=f"با لینک من رایگان VPN بگیر! 👇\n{referral_link}")]
            ]
            if user.wallet >= free_threshold:
                kb_buttons.append([InlineKeyboardButton(text="🎁 دریافت کانفیگ رایگان", callback_data="buy_free_config")])
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Wallet Error for {message.from_user.id}: {e}")
        await message.answer("❌ خطایی در نمایش کیف پول رخ داد.")

@router.message(F.text == "👥 زیرمجموعه‌گیری")
async def referral_menu(message: Message, bot: Bot):
    try:
        async for session in get_db():
            user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one_or_none()
            if not user:
                await message.answer("⚠️ لطفاً ابتدا شماره تماس خود را ثبت کنید.")
                return
            refs_count = (await session.execute(select(func.count(User.id)).where(User.referred_by == user.referral_code))).scalar() or 0
            referral_reward = int(await get_setting(session, "referral_reward", "10000"))
            bot_username = await get_bot_username(session, bot)
            referral_link = f"https://t.me/{bot_username}?start={user.referral_code}"
            text = (
                f"👥 **زیرمجموعه‌گیری:**\n"
                f"👥 تعداد زیرمجموعه‌ها: `{refs_count}` نفر\n"
                f"🎁 پاداش هر زیرمجموعه: `{referral_reward:,}` تومان\n"
                f"🔗 **لینک اختصاصی شما:**\n`{referral_link}`\n"
                f"💡 **راهنما:**\n"
                f"• لینک بالا را برای دوستان خود ارسال کنید\n"
                f"• با هر ثبت‌نام و تایید شماره، پاداش به کیف پول شما اضافه می‌شود"
            )
            kb_buttons = [
                [InlineKeyboardButton(text="📋 کپی لینک", callback_data="copy_referral_link"),
                 InlineKeyboardButton(text="📤 اشتراک‌گذاری", switch_inline_query=f"با لینک من رایگان VPN بگیر! 👇\n{referral_link}")],
                [InlineKeyboardButton(text="🔙 بازگشت به منو", callback_data="back_to_main_menu")]
            ]
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")
    except Exception as e: logging.error(f"Referral Error for {message.from_user.id}: {e}")

@router.callback_query(F.data == "pay_card")
async def pay_card_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("💳 **افزایش موجودی**\nلطفاً مبلغ دلخواه خود را به تومان وارد کنید (حداقل ۱۰,۰۰۰ تومان):", parse_mode="Markdown")
    await state.set_state(PaymentState.waiting_for_amount)
    await callback.answer()

@router.callback_query(F.data == "copy_referral_link")
async def copy_referral_link_handler(callback: CallbackQuery, bot: Bot):
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == callback.from_user.id))).scalar_one_or_none()
    if not user:
        await callback.answer("❌ کاربر یافت نشد", show_alert=True)
        return
    bot_username = await get_bot_username(session, bot)
    referral_link = f"https://t.me/{bot_username}?start={user.referral_code}"
    await callback.message.answer(f"🔗 **لینک دعوت اختصاصی شما:**\n<code>{referral_link}</code>\n💡 _روی لینک بالا ضربه بزنید تا کپی شود._", parse_mode="HTML")
    await callback.answer("✅ لینک ارسال شد", show_alert=False)

@router.callback_query(F.data == "buy_free_config")
async def buy_free_config(callback: CallbackQuery, bot: Bot):
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == callback.from_user.id))).scalar_one_or_none()
        free_threshold = int(await get_setting(session, "free_config_threshold", "50000"))
        
        # ۱. بررسی تعداد سرویس‌های فعال رایگان (حداکثر ۱۰)
        active_free_count = (await session.execute(select(func.count(ConfigProfile.id)).where(
            ConfigProfile.telegram_id == callback.from_user.id,
            ConfigProfile.username.like("free_%"),
            ConfigProfile.is_active == True
        ))).scalar() or 0
        
        if active_free_count >= 10:
            return await callback.answer("❌ شما ۱۰ سرویس رایگان فعال دارید. تا زمانی که آنها تمام نشوند، نمی‌توانید سرویس جدید بگیرید.", show_alert=True)
            
        # ۲. بررسی فاکتورهای رایگان قدیمی‌تر از ۱ روز
        now_ms = int(time.time() * 1000)
        day_ms = 24 * 60 * 60 * 1000
        old_free_count = (await session.execute(select(func.count(ConfigProfile.id)).where(
            ConfigProfile.telegram_id == callback.from_user.id,
            ConfigProfile.username.like("free_%"),
            ConfigProfile.is_active == True,
            ConfigProfile.expiry_time < (now_ms - day_ms)
        ))).scalar() or 0
        
        if old_free_count > 0:
             return await callback.answer("❌ شما سرویس‌های رایگان منقضی شده یا قدیمی دارید که باید تعیین تکلیف شوند.", show_alert=True)

        if not user or user.wallet < free_threshold:
            return await callback.answer("موجودی کافی نیست!", show_alert=True)
            
        # کسر فوری موجودی
        user.wallet -= free_threshold
        await session.commit()
        
    free_vol = int(await get_setting(session, "free_config_volume_gb", "10"))
    free_dur = int(await get_setting(session, "free_config_duration_days", "30"))
    email = f"free_{user.telegram_id}_{int(time.time())}"
    selected_ids = await get_selected_inbound_ids()
    res = await panel_api.add_client(email=email, total_gb=free_vol, expiry_hours=free_dur*24, inbound_ids=selected_ids if selected_ids else None)
    
    if res["success"]:
        async for session in get_db():
            # Refresh user
            user = (await session.execute(select(User).where(User.telegram_id == callback.from_user.id))).scalar_one_or_none()
            inbound_ids_str = ",".join(str(x) for x in res.get("inbound_ids", []))
            session.add(ConfigProfile(
                telegram_id=user.telegram_id, username=email, sub_link=res["sub_link"],
                sub_id=res.get("sub_id"), is_active=True, expiry_time=res["expiry_time_ms"],
                volume_gb=free_vol, duration_days=free_dur, inbound_ids=inbound_ids_str
            ))
            await session.commit()
            
        await send_config_package(
            bot=bot, user_id=user.telegram_id, sub_link=res['sub_link'],
            username=email, volume_display=f"{free_vol} GB", duration_display=f"{free_dur} روز"
        )
    else:
        # بازگشت وجه در صورت شکست
        async for session in get_db():
            user = (await session.execute(select(User).where(User.telegram_id == callback.from_user.id))).scalar_one_or_none()
            user.wallet += free_threshold
            await session.commit()
        await callback.answer(f"❌ خطا: {res['msg']}", show_alert=True)

@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    from bot.handlers.start import MAIN_MENU
    await callback.message.answer("منوی اصلی:", reply_markup=MAIN_MENU)
    await callback.answer()
