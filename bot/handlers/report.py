from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from bot.database import get_db, User, Payment, ConfigProfile, Ticket
from bot.auth import is_admin

router = Router()

@router.message(F.text == "📊 گزارش‌ها")
async def admin_reports(message: Message):
    if not await is_admin(message.from_user.id): return
    
    now = datetime.utcnow()
    today_str = now.strftime('%Y-%m-%d')
    yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    async for session in get_db():
        # --- درآمد امروز ---
        today_sum = (await session.execute(
            select(func.sum(Payment.amount)).where(
                and_(Payment.status == "approved", func.date(Payment.created_at) == today_str)
            )
        )).scalar() or 0
        today_count = (await session.execute(
            select(func.count(Payment.id)).where(
                and_(Payment.status == "approved", func.date(Payment.created_at) == today_str)
            )
        )).scalar() or 0
        
        # --- درآمد دیروز ---
        yesterday_sum = (await session.execute(
            select(func.sum(Payment.amount)).where(
                and_(Payment.status == "approved", func.date(Payment.created_at) == yesterday_str)
            )
        )).scalar() or 0
        yesterday_count = (await session.execute(
            select(func.count(Payment.id)).where(
                and_(Payment.status == "approved", func.date(Payment.created_at) == yesterday_str)
            )
        )).scalar() or 0
        
        # --- درآمد ۷ روز و ۳۰ روز ---
        week_sum = (await session.execute(
            select(func.sum(Payment.amount)).where(
                and_(Payment.status == "approved", Payment.created_at >= week_ago)
            )
        )).scalar() or 0
        
        month_sum = (await session.execute(
            select(func.sum(Payment.amount)).where(
                and_(Payment.status == "approved", Payment.created_at >= month_ago)
            )
        )).scalar() or 0
        
        # --- کل درآمد ---
        total_sum = (await session.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "approved")
        )).scalar() or 0
        
        # --- در انتظار تایید ---
        pending_count = (await session.execute(
            select(func.count(Payment.id)).where(Payment.status == "pending")
        )).scalar() or 0
        
        # --- کاربران ---
        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
        verified_users = (await session.execute(
            select(func.count(User.id)).where(User.phone_verified == True)
        )).scalar() or 0
        
        # --- سرویس‌ها ---
        total_configs = (await session.execute(select(func.count(ConfigProfile.id)))).scalar() or 0
        active_configs = (await session.execute(
            select(func.count(ConfigProfile.id)).where(ConfigProfile.is_active == True)
        )).scalar() or 0
        
        # --- تیکت‌ها ---
        open_tickets = (await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == "open")
        )).scalar() or 0
        replied_tickets = (await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == "admin_replied")
        )).scalar() or 0

    def fmt(val):
        return f"{val:,}" if val else "0"

    text = (
        f"📊 **گزارش جامع سیستم**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 **درآمد و پرداخت‌ها:**\n"
        f"├ 📅 **امروز:** `{fmt(today_sum)}` T ({today_count} تراکنش)\n"
        f"├ 📆 **دیروز:** `{fmt(yesterday_sum)}` T ({yesterday_count} تراکنش)\n"
        f"├ 🗓 **۷ روز اخیر:** `{fmt(week_sum)}` T\n"
        f"├ 🗓 **۳۰ روز اخیر:** `{fmt(month_sum)}` T\n"
        f"└ 📈 **کل درآمد:** `{fmt(total_sum)}` T\n"
        f"⏳ **پرداخت‌های در انتظار تایید:** `{pending_count}` مورد\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 **آمار کاربران:**\n"
        f"├ 👤 **کل کاربران:** `{total_users}`\n"
        f"└ ✅ **تایید شده (شماره):** `{verified_users}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 **آمار سرویس‌ها:**\n"
        f"├ 🟢 **فعال:** `{active_configs}`\n"
        f"└ 📊 **کل:** `{total_configs}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 **آمار تیکت‌ها:**\n"
        f"├ 🟢 **باز (در انتظار پاسخ):** `{open_tickets}`\n"
        f"└ 🟡 **پاسخ داده شده:** `{replied_tickets}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await message.answer(text, parse_mode="Markdown")