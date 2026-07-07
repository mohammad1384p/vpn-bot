from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import select, desc
from bot.database import User, get_db

router = Router()

RANKS = {
    "bronze": {"name": "🥉 برنز", "min_spent": 0},
    "silver": {"name": "🥈 نقره‌ای", "min_spent": 100000},
    "gold": {"name": "🥇 طلایی", "min_spent": 500000},
    "platinum": {"name": "💎 پلاتینیوم", "min_spent": 2000000},
}

def calculate_rank(total_spent):
    for rank_key in ["platinum", "gold", "silver", "bronze"]:
        if total_spent >= RANKS[rank_key]["min_spent"]: return rank_key
    return "bronze"

@router.message(F.text == "🏆 رتبه من")
async def my_rank(message: Message):
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one_or_none()
    if not user: return await message.answer("❌ ابتدا شماره خود را ثبت کنید.")
    new_rank = calculate_rank(user.total_spent)
    if user.rank != new_rank:
        async for session in get_db():
            user.rank = new_rank
            await session.commit()
    async for session in get_db():
        result = await session.execute(select(User).where(User.total_spent > 0).order_by(desc(User.total_spent)).limit(10))
        top_users = result.scalars().all()
    rank_info = RANKS[user.rank]
    next_rank = None
    for r in ["silver", "gold", "platinum"]:
        if user.total_spent < RANKS[r]["min_spent"]:
            next_rank = r
            break
    text = f"🏆 **رتبه شما:** {rank_info['name']}\n💰 مجموع: `{user.total_spent:,}` T\n"
    if next_rank:
        needed = RANKS[next_rank]["min_spent"] - user.total_spent
        text += f"\n📈 برای **{RANKS[next_rank]['name']}**:\n🔸 `{needed:,}` T"
    else: text += "\n🎉 بالاترین رتبه!"
    text += "\n**🏅 برترین‌ها:**\n"
    for i, u in enumerate(top_users, 1):
        r_info = RANKS.get(u.rank, RANKS["bronze"])
        text += f"{i}. {r_info['name']} `{u.total_spent:,}` T\n"
    await message.answer(text, reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 بازگشت به منو")]], resize_keyboard=True), parse_mode="Markdown")
