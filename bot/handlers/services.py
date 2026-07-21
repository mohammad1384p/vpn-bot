from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, desc
from bot.database import ConfigProfile, User, get_db
from bot.panel_api import panel_api
import time

router = Router()

def format_bytes(bytes_val: int) -> str:
    if not bytes_val or bytes_val <= 0: return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}" if bytes_val >= 10 else f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"

def format_remaining_time(expiry_ms: int) -> str:
    if not expiry_ms or expiry_ms <= 0: return "♾️ نامحدود"
    now_ms = int(time.time() * 1000)
    diff_ms = expiry_ms - now_ms
    if diff_ms <= 0: return "⛔ منقضی"
    diff_hours = diff_ms / (1000 * 3600)
    diff_days = int(diff_hours // 24)
    remaining_hours = int(diff_hours % 24)
    if diff_days > 0: return f"⏱ {diff_days} روز {remaining_hours} ساعت"
    elif remaining_hours > 0: return f"⏱ {remaining_hours} ساعت"
    else:
        diff_minutes = int((diff_ms / (1000 * 60)) % 60)
        return f"⏱ {diff_minutes} دقیقه"

async def update_config_traffic_from_panel(config):
    if not config.username or not config.server_id: return None
    res = await panel_api.get_client_traffic(config.username, config.server_id)
    if res["success"]:
        config.used_traffic_bytes = res.get("used", 0)
        if res.get("expiryTime"): config.expiry_time = res["expiryTime"]
        now_ms = int(time.time() * 1000)
        if res.get("expiryTime", 0) and res["expiryTime"] < now_ms and res["expiryTime"] != 0: config.is_active = False
        elif res.get("enable") == False: config.is_active = False
        return res
    return None

@router.message(F.text == "📦 سرویس‌های من")
async def my_services_menu(message: Message):
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one_or_none()
        if not user:
            await message.answer("⚠️ لطفاً ابتدا /start را بزنید.")
            return
        from bot.handlers.start import requires_phone_auth, PHONE_KB
        if requires_phone_auth(user):
            await message.answer("🔐 چون با لینک زیرمجموعه وارد شده‌اید، ابتدا شماره تماس خود را تایید کنید.", reply_markup=PHONE_KB)
            return
        result = await session.execute(select(ConfigProfile).where(ConfigProfile.telegram_id == message.from_user.id).order_by(desc(ConfigProfile.id)))
        configs = result.scalars().all()
    if not configs:
        await message.answer("📦 **سرویس‌های شما:**\n⚠️ هنوز سرویسی ندارید.", parse_mode="Markdown")
        return
    text = "📦 **سرویس‌های شما:**\n"
    kb_buttons = []
    for config in configs:
        if config.is_test: status_icon, type_label = "🧪", "تست"
        elif not config.is_active: status_icon, type_label = "⛔", "منقضی"
        else: status_icon, type_label = "✅", "فعال"
        remaining = format_remaining_time(config.expiry_time) if config.expiry_time and not config.is_unlimited_time else "♾️ نامحدود"
        text += f"{status_icon} **{config.username}** ({type_label})\n└ {remaining}\n"
        kb_buttons.append([InlineKeyboardButton(text=f"{status_icon} {config.username}", callback_data=f"service_detail:{config.id}")])
    kb_buttons.append([InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="services_refresh")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.callback_query(F.data == "services_refresh")
async def refresh_services(callback: CallbackQuery):
    await callback.answer("🔄 در حال بروزرسانی...", show_alert=False)
    async for session in get_db():
        result = await session.execute(select(ConfigProfile).where(ConfigProfile.telegram_id == callback.from_user.id))
        configs = result.scalars().all()
        for config in configs: await update_config_traffic_from_panel(config)
        await session.commit()
    await callback.message.delete()
    class FakeMsg:
        def __init__(self, cb):
            self.from_user = cb.from_user
            self.chat = cb.message.chat
        async def answer(self, *a, **k): return await callback.message.answer(*a, **k)
    await my_services_menu(FakeMsg(callback))

@router.callback_query(F.data.startswith("service_detail:"))
async def service_detail(callback: CallbackQuery):
    config_id = int(callback.data.split(":")[1])
    async for session in get_db():
        config = (await session.execute(select(ConfigProfile).where(ConfigProfile.id == config_id, ConfigProfile.telegram_id == callback.from_user.id))).scalar_one_or_none()
    if not config: return await callback.answer("❌ یافت نشد", show_alert=True)
    res = await update_config_traffic_from_panel(config)
    async for session in get_db(): await session.commit()
    
    if res and res["success"]:
        used_bytes = res.get("used", 0)
        total_bytes = res.get("total", 0)
        used_str = format_bytes(used_bytes)
        if total_bytes > 0:
            percent = (used_bytes / total_bytes) * 100
            filled = int((percent / 100) * 10)
            progress = "█" * filled + "░" * (10 - filled)
            total_str = format_bytes(total_bytes)
            usage_info = f"{progress} {percent:.1f}%\n📊 `{used_str}` از `{total_str}`"
        else: usage_info = f"♾️ **نامحدود**\n📊 مصرف: `{used_str}`"
    else:
        used_bytes = config.used_traffic_bytes or 0
        used_str = format_bytes(used_bytes)
        if config.is_unlimited_volume or config.volume_gb <= 0: usage_info = f"♾️ **نامحدود**\n📊 مصرف: `{used_str}`"
        else:
            total_str = f"{config.volume_gb} GB"
            usage_info = f"📊 `{used_str}` از `{total_str}`"

    if config.is_test: status_text = "🧪 **تست**"
    elif config.is_active: status_text = "✅ **فعال**"
    else: status_text = "⛔ **منقضی**"
    
    remaining = format_remaining_time(config.expiry_time) if not config.is_unlimited_time else "♾️ نامحدود"
    inbounds_count = len(config.inbound_ids.split(",")) if config.inbound_ids else "?"
    duration_display = "♾️ نامحدود" if config.is_unlimited_time or config.duration_days <= 0 else f"`{config.duration_days} روز`"
    volume_display = "♾️ نامحدود" if config.is_unlimited_volume or config.volume_gb <= 0 else f"`{config.volume_gb} GB`"
    
    text = (
        f"📦 **جزئیات سرویس**\n"
        f"🆔 `{config.username}`\n"
        f"📊 {status_text}\n"
        f"📈 **حجم:**\n{usage_info}\n"
        f"⏳ **زمان:**\n{remaining}\n"
        f"📦 حجم: {volume_display}\n"
        f"📅 مدت: {duration_display}\n"
        f"🎯 `{inbounds_count}` اینباند\n"
        f"🔗 **لینک:**\n<code>{config.sub_link}</code>"
    )
    kb_buttons = [[InlineKeyboardButton(text="📋 کپی لینک", callback_data=f"copy_sub:{config.id}")]]
    if not config.is_active and not config.is_test:
        kb_buttons.append([InlineKeyboardButton(text="🔄 تمدید", callback_data=f"renew_service:{config.id}")])
    kb_buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_services")])
    try: await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="HTML")
    except TelegramBadRequest: await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="HTML")

@router.callback_query(F.data == "back_to_services")
async def back_to_services(callback: CallbackQuery):
    class FakeMsg:
        def __init__(self, cb):
            self.from_user = cb.from_user
            self.chat = cb.message.chat
        async def answer(self, *a, **k): return await callback.message.answer(*a, **k)
    await callback.message.delete()
    await my_services_menu(FakeMsg(callback))

@router.callback_query(F.data.startswith("copy_sub:"))
async def copy_sub_link(callback: CallbackQuery):
    config_id = int(callback.data.split(":")[1])
    async for session in get_db():
        config = (await session.execute(select(ConfigProfile).where(ConfigProfile.id == config_id, ConfigProfile.telegram_id == callback.from_user.id))).scalar_one_or_none()
    if config:
        await callback.message.answer(f"🔗 **{config.username}:**\n<code>{config.sub_link}</code>", parse_mode="HTML")
        await callback.answer("✅ ارسال شد")
    else: await callback.answer("❌ یافت نشد", show_alert=True)

@router.callback_query(F.data.startswith("renew_service:"))
async def renew_service_redirect(callback: CallbackQuery):
    await callback.answer("از بخش «🔄 تمدید» استفاده کنید.", show_alert=True)
