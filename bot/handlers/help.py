from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from bot.database import get_db, get_setting
from bot.handlers.start import MAIN_MENU

router = Router()

HELP_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🤖 اندروید"), KeyboardButton(text="🍎 آیفون")],
        [KeyboardButton(text="💻 ویندوز"), KeyboardButton(text="🔙 بازگشت به منو")]
    ],
    resize_keyboard=True
)

@router.message(F.text == "🎓 راهنما")
async def btn_help(message: Message):
    await message.answer("🎓 **راهنمای اتصال:**", reply_markup=HELP_MENU, parse_mode="Markdown")

@router.message(F.text.in_(["🤖 اندروید", "🍎 آیفون", "💻 ویندوز"]))
async def show_os_help(message: Message):
    os_map = {"🤖 اندروید": "help_android", "🍎 آیفون": "help_ios", "💻 ویندوز": "help_windows"}
    async for session in get_db():
        link = await get_setting(session, os_map[message.text], "")
    if not link:
        await message.answer("⚠️ آموزش برای این سیستم عامل هنوز تنظیم نشده است.")
        return
    await message.answer(
        f"📱 **آموزش اتصال ({message.text}):**\n"
        f"🔗 [کلیک کنید و آموزش را مشاهده نمایید]({link})\n"
        f"📋 یا لینک زیر را کپی کنید:\n`{link}`",
        parse_mode="Markdown", disable_web_page_preview=False
    )
