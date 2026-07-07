import qrcode
import io
from aiogram.types import BufferedInputFile
from aiogram import Bot
from bot.database import get_db, get_setting

def generate_qr_file(data: str) -> BufferedInputFile:
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    bio.name = "config_qr.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return BufferedInputFile(bio.read(), filename="config_qr.png")

async def send_config_with_tutorial(bot: Bot, user_id: int, sub_link: str, username: str = "", inbounds_count: str = None, title: str = "✅ **پرداخت تایید شد!**", extra_info: str = ""):
    qr_file = generate_qr_file(sub_link)
    
    async for session in get_db():
        help_android = await get_setting(session, "help_android", "")
        help_ios = await get_setting(session, "help_ios", "")
        help_windows = await get_setting(session, "help_windows", "")
        
    tutorial_text = "🎓 **آموزش اتصال:**\n"
    if help_android: tutorial_text += f"🤖 اندروید: [کلیک کنید]({help_android})\n"
    if help_ios: tutorial_text += f"🍎 آیفون: [کلیک کنید]({help_ios})\n"
    if help_windows: tutorial_text += f"💻 ویندوز: [کلیک کنید]({help_windows})\n"
    if not (help_android or help_ios or help_windows):
        tutorial_text += "برای مشاهده آموزش‌ها، از منوی اصلی دکمه «🎓 راهنما» را بزنید.\n"
        
    caption = f"{title}\n\n"
    if username: caption += f"🔗 `{username}`\n"
    if inbounds_count and inbounds_count != "?": caption += f"🎯 `{inbounds_count}` اینباند\n"
    if extra_info: caption += f"{extra_info}\n"
    caption += f"🔗 **لینک ساب:**\n<code>{sub_link}</code>\n\n{tutorial_text}\n💡 _برای اتصال، لینک بالا را کپی کرده یا از QR Code استفاده کنید._"
    
    try:
        await bot.send_photo(user_id, qr_file, caption=caption, parse_mode="HTML")
    except Exception:
        await bot.send_message(user_id, caption, parse_mode="HTML")
