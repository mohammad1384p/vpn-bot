import re, logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from sqlalchemy import select
from bot.database import User, get_db, get_channel_ids, get_setting
from bot.config import Config

router = Router()

def normalize_phone(phone: str) -> str:
    if not phone: return ""
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('0') and len(digits) == 11: digits = '98' + digits[1:]
    return digits

def is_iran_phone(phone: str) -> bool:
    digits = normalize_phone(phone)
    return len(digits) == 12 and digits.startswith('98') and digits[2] == '9'

def format_phone_display(phone: str) -> str:
    digits = normalize_phone(phone)
    if len(digits) == 12: return f"+{digits[:2]} {digits[2:5]} {digits[5:8]} {digits[8:]}"
    return phone

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛒 خرید کانفیگ"), KeyboardButton(text="🔄 تمدید")],
        [KeyboardButton(text="📦 سرویس‌های من"), KeyboardButton(text="🎁 اکانت تست")],
        [KeyboardButton(text="👥 کیف پول"), KeyboardButton(text="👥 زیرمجموعه‌گیری")],
        [KeyboardButton(text="🎓 راهنما"), KeyboardButton(text="🎫 پشتیبانی")],
        [KeyboardButton(text="🏆 رتبه من"), KeyboardButton(text="🎟 کد تخفیف")]
    ],
    resize_keyboard=True, is_persistent=True
)

PHONE_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 ارسال شماره تماس", request_contact=True)]],
    resize_keyboard=True
)

async def check_user_membership(bot: Bot, user_id: int):
    channel_ids = await get_channel_ids()
    if not channel_ids: return []
    not_joined = []
    for chat_id in channel_ids:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ["left", "kicked"]:
                chat_info = await bot.get_chat(chat_id)
                username = chat_info.username if chat_info.username else str(chat_id).replace("-100", "")
                not_joined.append({"id": chat_id, "username": username, "title": chat_info.title or "کانال"})
        except Exception: pass
    return not_joined

@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot):
    parts = message.text.split()
    ref_code = parts[1] if len(parts) > 1 else None
    if ref_code:
        try:
            async for session in get_db():
                result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
                user = result.scalar_one_or_none()
                if not user:
                    new_user = User(telegram_id=message.from_user.id, phone_verified=False, referral_code=str(message.from_user.id), referred_by=ref_code, wallet=0, rank="bronze", total_spent=0)
                    session.add(new_user)
                    await session.commit()
                else:
                    if not user.referred_by and ref_code != str(user.telegram_id):
                        user.referred_by = ref_code
                        await session.commit()
        except Exception as e: logging.error(f"Error saving ref_code at /start: {e}")

    not_joined_channels = await check_user_membership(bot, message.from_user.id)
    if not_joined_channels:
        kb_buttons = [[InlineKeyboardButton(text=f"📢 عضویت در {ch['title']}", url=f"https://t.me/{ch['username']}")] for ch in not_joined_channels]
        cb_data = f"check_join:{ref_code}" if ref_code else "check_join"
        kb_buttons.append([InlineKeyboardButton(text="✅ بررسی عضویت", callback_data=cb_data)])
        await message.answer("👋 برای استفاده از ربات، در کانال‌های زیر عضو شوید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))
        return
    
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if user and user.is_blocked:
            await message.answer("⛔ **دسترسی شما مسدود شده است.**\nبرای رفع مسدودیت با پشتیبانی تماس بگیرید.", parse_mode="Markdown")
            return
    
    await show_main_menu(message, ref_code)

@router.callback_query(F.data.startswith("check_join"))
async def check_join_callback(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    ref_code = parts[1] if len(parts) > 1 else None
    await callback.answer("⏳ در حال بررسی...")
    not_joined_channels = await check_user_membership(bot, callback.from_user.id)
    if not not_joined_channels:
        await callback.message.delete()
        class FakeMsg:
            def __init__(self, cb, ref):
                self.from_user = cb.from_user
                self.chat = cb.message.chat
                self._ref_code = ref
            async def answer(self, *a, **k): return await callback.message.answer(*a, **k)
        await show_main_menu(FakeMsg(callback, ref_code), ref_code)
    else:
        kb_buttons = [[InlineKeyboardButton(text=f"📢 عضویت در {ch['title']}", url=f"https://t.me/{ch['username']}")] for ch in not_joined_channels]
        cb_data = f"check_join:{ref_code}" if ref_code else "check_join"
        kb_buttons.append([InlineKeyboardButton(text="✅ بررسی مجدد", callback_data=cb_data)])
        await callback.message.edit_text("⚠️ هنوز در تمام کانال‌ها عضو نشده‌اید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))

async def show_main_menu(message: Message, ref_code: str = None):
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=message.from_user.id, phone_verified=False, referral_code=str(message.from_user.id), referred_by=ref_code, wallet=0, rank="bronze", total_spent=0)
            session.add(user)
            await session.commit()
        else:
            if ref_code and not user.referred_by and ref_code != str(user.telegram_id):
                user.referred_by = ref_code
                await session.commit()
                
    has_referral = bool(ref_code and ref_code != str(user.telegram_id)) or bool(user.referred_by and user.referred_by != str(user.telegram_id))
    if has_referral and not user.phone_verified:
        await message.answer("🔐 **تکمیل ثبت‌نام زیرمجموعه:**\nبرای فعال‌سازی حساب و دریافت هدیه خوش‌آمدگویی، لطفاً شماره تماس خود را تایید کنید.", reply_markup=PHONE_KB, parse_mode="Markdown")
        return
    await message.answer(f"سلام {message.from_user.first_name} عزیز! 👋\nاز منوی زیر انتخاب کنید:", reply_markup=MAIN_MENU)

@router.message(F.contact)
async def handle_contact(message: Message, bot: Bot):
    if not message.contact or not message.contact.phone_number:
        await message.answer("❌ شماره دریافت نشد.")
        return
    phone = message.contact.phone_number
    if not is_iran_phone(phone):
        await message.answer("❌ **شماره غیر ایرانی!**\nفقط شماره‌های ایران پذیرفته می‌شود.", parse_mode="Markdown")
        return
    normalized = normalize_phone(phone)
    display_phone = format_phone_display(phone)
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if user and user.phone_verified:
            await message.answer("✅ شماره شما قبلاً تایید شده است.", reply_markup=MAIN_MENU)
            return
        existing = (await session.execute(select(User).where(User.phone == normalized))).scalar_one_or_none()
        if existing and existing.telegram_id != message.from_user.id:
            await message.answer("⚠️ این شماره قبلاً ثبت شده است.")
            return
        is_new_verify = False
        if existing and existing.telegram_id == message.from_user.id:
            if not existing.phone_verified: is_new_verify = True
            existing.phone_verified = True
            existing.phone = normalized
            await session.commit()
            user = existing
        else:
            is_new_verify = True
            if not user:
                user = User(telegram_id=message.from_user.id, phone=normalized, phone_verified=True, referral_code=str(message.from_user.id), wallet=0, rank="bronze", total_spent=0)
                session.add(user)
            else:
                user.phone = normalized
                user.phone_verified = True
                if not user.referral_code or user.referral_code.startswith("manual_"): user.referral_code = str(message.from_user.id)
            await session.commit()
            
        if is_new_verify and user.referred_by and user.referred_by != str(user.telegram_id):
            ref_user = (await session.execute(select(User).where(User.referral_code == user.referred_by))).scalar_one_or_none()
            if ref_user:
                reward = int(await get_setting(session, "referral_reward", "10000"))
                ref_user.wallet += reward
                await session.commit()
                try:
                    await bot.send_message(ref_user.telegram_id, f"🎉 **تبریک! زیرمجموعه جدید تایید شد.**\n👤 کاربر `{user.telegram_id}` شماره خود را تایید کرد.\n💰 مبلغ `{reward:,}` تومان به کیف پول شما اضافه شد.", parse_mode="Markdown")
                except Exception as e: logging.error(f"Failed to send signup reward notification: {e}")
                
    await message.answer(f"✅ **شماره شما با موفقیت تایید شد!**\n📞 `{display_phone}`\nاکنون می‌توانید از تمامی امکانات ربات استفاده کنید.", reply_markup=MAIN_MENU, parse_mode="Markdown")

@router.message(Command("verify_user"))
async def admin_verify_user(message: Message, bot: Bot):
    from bot.auth import is_admin
    if not await is_admin(message.from_user.id): return
    try:
        parts = message.text.split()
        if len(parts) < 2: return await message.answer("❌ فرمت: `/verify_user [id] [phone]`", parse_mode="Markdown")
        user_id = int(parts[1])
        phone = parts[2] if len(parts) > 2 else f"manual_{user_id}"
        async for session in get_db():
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalar_one_or_none()
            is_new_verify = False
            if not user:
                user = User(telegram_id=user_id, phone=phone, phone_verified=True, referral_code=str(user_id), wallet=0, rank="bronze", total_spent=0)
                session.add(user)
                is_new_verify = True
            else:
                if not user.phone_verified:
                    is_new_verify = True
                    user.phone = phone
                    user.phone_verified = True
            await session.commit()
            if is_new_verify and user.referred_by and user.referred_by != str(user.telegram_id):
                ref_user = (await session.execute(select(User).where(User.referral_code == user.referred_by))).scalar_one_or_none()
                if ref_user:
                    reward = int(await get_setting(session, "referral_reward", "10000"))
                    ref_user.wallet += reward
                    await session.commit()
                    try: await bot.send_message(ref_user.telegram_id, f"🎉 تبریک! زیرمجموعه شما ({user.telegram_id}) توسط ادمین تایید شد.\n💰 مبلغ `{reward:,}` تومان به کیف پول شما اضافه شد.", parse_mode="Markdown")
                    except Exception as e: logging.error(f"Failed to send admin verify reward: {e}")
        await message.answer(f"✅ کاربر `{user_id}` تایید شد.", parse_mode="Markdown")
        try: await bot.send_message(user_id, "🎉 حساب شما تایید شد!", reply_markup=MAIN_MENU, parse_mode="Markdown")
        except: pass
    except Exception as e: await message.answer(f"❌ خطا: {e}")

@router.message(Command("unverify_user"))
async def admin_unverify_user(message: Message):
    from bot.auth import is_admin
    if not await is_admin(message.from_user.id): return
    try:
        user_id = int(message.text.split()[1])
        async for session in get_db():
            user = (await session.execute(select(User).where(User.telegram_id == user_id))).scalar_one_or_none()
            if user:
                user.phone_verified = False
                await session.commit()
        await message.answer(f"✅ تایید کاربر `{user_id}` لغو شد.", parse_mode="Markdown")
    except: await message.answer("❌ فرمت: `/unverify_user [id]`", parse_mode="Markdown")

@router.message(Command("reset_phone"))
async def admin_reset_phone(message: Message, bot: Bot):
    from bot.auth import is_admin
    if not await is_admin(message.from_user.id): return
    try:
        user_id = int(message.text.split()[1])
        async for session in get_db():
            user = (await session.execute(select(User).where(User.telegram_id == user_id))).scalar_one_or_none()
            if user:
                user.phone = None
                user.phone_verified = False
                await session.commit()
        await message.answer(f"✅ شماره `{user_id}` ریست شد.", parse_mode="Markdown")
        try: await bot.send_message(user_id, "🔄 شماره شما ریست شد.", reply_markup=PHONE_KB)
        except: pass
    except Exception as e: await message.answer(f"❌ خطا: {e}")

@router.message(F.text == "🔙 بازگشت به منو")
async def global_back_to_menu(message: Message):
    await show_main_menu(message)
