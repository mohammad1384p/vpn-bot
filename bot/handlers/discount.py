from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

router = Router()

@router.message(F.text == "🎟 کد تخفیف")
async def ask_discount(message: Message):
    await message.answer(
        "💡 **راهنمای کد تخفیف:**\n\n"
        "شما می‌توانید کد تخفیف خود را مستقیماً در مراحل **🛒 خرید کانفیگ** یا **🔄 تمدید** وارد کنید.\n\n"
        "🎟 اگر کد تخفیفی دارید، هنگام انتخاب بسته یا تمدید، روی دکمه «اعمال کد تخفیف» کلیک کنید.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛒 خرید کانفیگ")], [KeyboardButton(text="🔄 تمدید")], [KeyboardButton(text="🔙 بازگشت به منو")]], resize_keyboard=True)
    )
