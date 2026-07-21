import time
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message
from sqlalchemy import select, func
from bot.database import User, ConfigProfile, get_db, get_setting
from bot.panel_api import panel_api
from bot.handlers.inbounds import get_selected_inbound_ids
from bot.handlers.start import PHONE_KB, requires_phone_auth
from bot.utils.helpers import send_config_package

router = Router()

@router.message(F.text == "🎁 اکانت تست")
async def get_test_account(message: Message, bot: Bot):
    await bot.send_chat_action(message.from_user.id, "typing")
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one_or_none()
        if not user:
            return await message.answer("⚠️ لطفاً ابتدا /start را بزنید.")
        if requires_phone_auth(user):
            return await message.answer("🔐 چون با لینک زیرمجموعه وارد شده‌اید، برای دریافت اکانت تست ابتدا شماره تماس خود را تایید کنید.", reply_markup=PHONE_KB)
        cooldown_hours = int(await get_setting(session, "test_cooldown_hours", "24"))
        max_test = int(await get_setting(session, "max_test_per_user", "1"))
        volume_mb = int(await get_setting(session, "test_volume_mb", "100"))
        duration_hours = int(await get_setting(session, "test_duration_hours", "1"))
        
    if user.last_test_time:
        time_passed = datetime.utcnow() - user.last_test_time
        if time_passed < timedelta(hours=cooldown_hours):
            remaining = cooldown_hours - (time_passed.total_seconds() / 3600)
            return await message.answer(f"⏳ **{remaining:.1f} ساعت صبر کنید.**", parse_mode="Markdown")
            
    async for session in get_db():
        test_count = (await session.execute(select(func.count(ConfigProfile.id)).where(
            ConfigProfile.telegram_id == message.from_user.id, ConfigProfile.is_test == True, ConfigProfile.is_active == True
        ))).scalar() or 0
    if test_count >= max_test:
        return await message.answer(f"⚠️ **محدودیت تست**\nحداکثر `{max_test}` اکانت تست فعال.\n📊 فعلی: `{test_count}`", parse_mode="Markdown")
        
    email = f"test_{user.telegram_id}_{int(time.time())}"
    selected_ids = await get_selected_inbound_ids()
    res = await panel_api.add_client(
        email=email, total_gb=volume_mb/1024, expiry_hours=duration_hours,
        inbound_ids=selected_ids if selected_ids else None
    )
    if res["success"]:
        user.last_test_time = datetime.utcnow()
        inbound_ids_str = ",".join(str(x) for x in res.get("inbound_ids", []))
        async for session in get_db():
            session.add(ConfigProfile(
                telegram_id=user.telegram_id, username=email, sub_link=res["sub_link"],
                sub_id=res.get("sub_id"), is_active=True, expiry_time=res["expiry_time_ms"],
                volume_gb=max(1, volume_mb//1024), duration_days=1,
                inbound_ids=inbound_ids_str, is_test=True
            ))
            await session.commit()
            
        await send_config_package(
            bot=bot, user_id=message.from_user.id, sub_link=res['sub_link'],
            username=email, volume_display=f"{volume_mb} MB", duration_display=f"{duration_hours} ساعت", is_test=True
        )
    else:
        await message.answer(f"❌ خطا: {res['msg']}")
