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
        active_paid_configs = (await session.execute(
            select(func.count(ConfigProfile.id)).where(and_(ConfigProfile.is_active == True, ConfigProfile.is_test == False))
        )).scalar() or 0
        active_test_configs = (await session.execute(
            select(func.count(ConfigProfile.id)).where(and_(ConfigProfile.is_active == True, ConfigProfile.is_test == True))
        )).scalar() or 0
        inactive_configs = (await session.execute(
            select(func.count(ConfigProfile.id)).where(ConfigProfile.is_active == False)
        )).scalar() or 0

        # جزئیات سرویس‌های فعال (تا ۵ مورد از هر نوع)
        sample_paid_configs = (await session.execute(
            select(ConfigProfile).where(and_(ConfigProfile.is_active == True, ConfigProfile.is_test == False))
            .order_by(ConfigProfile.expiry_time.desc())
            .limit(5)
        )).scalars().all()
        sample_test_configs = (await session.execute(
            select(ConfigProfile).where(and_(ConfigProfile.is_active == True, ConfigProfile.is_test == True))
            .order_by(ConfigProfile.expiry_time.desc())
            .limit(5)
        )).scalars().all()
        
        # --- تیکت‌ها ---
        open_tickets = (await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == "open")
        )).scalar() or 0
        replied_tickets = (await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == "admin_replied")
        )).scalar() or 0

    def fmt(val):
        return f"{val:,}" if val else "0"

    # ساخت متن گزارش
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
        f"├ 🟢 **فعال (خریداری شده):** `{active_paid_configs}`\n"
        f"├ 🧪 **فعال (تست):** `{active_test_configs}`\n"
        f"├ 🔴 **غیرفعال:** `{inactive_configs}`\n"
        f"└ 📊 **کل:** `{total_configs}`\n"
    )
    
    # جزئیات سرویس‌های فعال
    if sample_paid_configs:
        text += "\n📝 **جزئیات سرویس‌ها (۵ مورد اخیر خریداری شده):**\n"
        for cfg in sample_paid_configs:
            expiry = datetime.fromtimestamp(cfg.expiry_time / 1000).strftime('%Y-%m-%d') if cfg.expiry_time else "نامحدود"
            usage = f"{cfg.used_traffic_bytes / (1024**3):.2f}GB / {cfg.volume_gb}GB" if not cfg.is_unlimited_volume else "نامحدود"
            text += f"• `{cfg.username}` | انقضا: `{expiry}` | مصرف: `{usage}`\n"
    if sample_test_configs:
        text += "\n📝 **جزئیات سرویس‌ها (۵ مورد اخیر تست):**\n"
        for cfg in sample_test_configs:
            expiry = datetime.fromtimestamp(cfg.expiry_time / 1000).strftime('%Y-%m-%d') if cfg.expiry_time else "نامحدود"
            usage = f"{cfg.used_traffic_bytes / (1024**3):.2f}GB / {cfg.volume_gb}GB" if not cfg.is_unlimited_volume else "نامحدود"
            text += f"• `{cfg.username}` | انقضا: `{expiry}` | مصرف: `{usage}`\n"

    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 **آمار تیکت‌ها:**\n"
        f"├ 🟢 **باز (در انتظار پاسخ):** `{open_tickets}`\n"
        f"└ 🟡 **پاسخ داده شده:** `{replied_tickets}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await message.answer(text, parse_mode="Markdown")