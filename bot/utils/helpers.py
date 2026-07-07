import qrcode
import io
from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from bot.database import get_db, get_setting, Admin
from bot.config import Config
from sqlalchemy import select

async def send_config_package(bot: Bot, user_id: int, sub_link: str, username: str, volume_display: str, duration_display: str, is_renew=False, is_test=False):
    # 1. Generate QR Code
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(sub_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    qr_photo = BufferedInputFile(bio.read(), filename=f"{username}_qr.png")

    # 2. Fetch Settings
    help_android, help_ios, help_windows, support_username = "", "", "", ""
    async for session in get_db():
        help_android = await get_setting(session, "help_android", "")
        help_ios = await get_setting(session, "help_ios", "")
        help_windows = await get_setting(session, "help_windows", "")
        support_username = await get_setting(session, "support_username", "")
    
    # 3. Format Message
    if is_test:
        action_text = "🎁 **اکانت تست شما آماده شد!**"
    elif is_renew:
        action_text = "🔄 **تمدید با موفقیت انجام شد!**"
    else:
        action_text = "✅ **خرید شما با موفقیت ثبت و فعال شد!**"
    
    text = (
        f"{action_text}\n\n"
        f"👤 **نام کاربری:** `{username}`\n"
        f"📦 **حجم:** {volume_display}\n"
        f"⏱ **مدت زمان:** {duration_display}\n\n"
        f"🔗 **لینک اشتراک (کلیک برای کپی):**\n"
        f"<code>{sub_link}</code>\n\n"
    )
    
    if not (help_android or help_ios or help_windows):
        text += "⚠️ _لینک آموزشی تنظیم نشده است._\n"
        
    text += f"\n🎫 **پشتیبانی:** @{support_username if support_username else 'Support'}\n"
    text += f"💡 _برای استفاده، لینک اشتراک را در برنامه خود وارد کنید یا از QR Code زیر استفاده نمایید._"

    # 4. Build Inline Keyboard (Glass Buttons for Guides)
    kb_buttons = []
    
    help_row = []
    if help_android: help_row.append(InlineKeyboardButton(text="🤖 آموزش اندروید", url=help_android))
    if help_ios: help_row.append(InlineKeyboardButton(text="🍎 آموزش آیفون", url=help_ios))
    if help_windows: help_row.append(InlineKeyboardButton(text="💻 آموزش ویندوز", url=help_windows))
    
    if help_row:
        kb_buttons.append(help_row)
        
    kb_buttons.append([InlineKeyboardButton(text="📦 سرویس‌های من", callback_data="back_to_services")])
    kb_buttons.append([InlineKeyboardButton(text="🏠 منوی اصلی", callback_data="back_to_main_menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    try:
        await bot.send_photo(
            chat_id=user_id,
            photo=qr_photo,
            caption=text,
            parse_mode="HTML",
            reply_markup=kb
        )
    except Exception:
        await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=kb)
        
    # 5. Notify Admins
    admin_ids = [Config.ADMIN_ID]
    try:
        async for session in get_db():
            result = await session.execute(select(Admin))
            admin_ids.extend([a.telegram_id for a in result.scalars().all()])
    except Exception:
        pass
        
    admin_ids = list(set(admin_ids))
    
    if is_test:
        type_text = "🧪 اکانت تست"
    elif is_renew:
        type_text = "🔄 تمدید"
    else:
        type_text = "🛒 خرید جدید"
        
    notify_text = (
        f"✅ **کانفیگ با موفقیت برای کاربر ارسال شد!**\n\n"
        f"👤 **آیدی کاربر:** `{user_id}`\n"
        f"🆔 **نام کاربری:** `{username}`\n"
        f"📦 **حجم:** {volume_display}\n"
        f"⏱ **مدت زمان:** {duration_display}\n"
        f"🎯 **نوع عملیات:** {type_text}"
    )
    
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, notify_text, parse_mode="Markdown")
        except Exception:
            pass
