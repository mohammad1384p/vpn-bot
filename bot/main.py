import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.types import FSInputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from bot.config import Config
from bot.database import init_db, migrate_db, get_db, ConfigProfile
from bot.panel_api import panel_api
from bot.utils import backup as backup_util
from sqlalchemy import select
from datetime import datetime
from bot.handlers import (
    start, services, shop, payment, test, help,
    packages, ticket, discount, ranking, renew,
    inbounds, config_settings, admin, content_links, monitoring, report
)
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def auto_backup_scheduler(bot: Bot):
    while True:
        await asyncio.sleep(86400)
        try:
            path = await backup_util.create_backup()
            await bot.send_document(Config.ADMIN_ID, FSInputFile(path), caption="🗳 Daily Backup")
            import os; os.remove(path)
        except Exception as e: logging.error(f"Backup Error: {e}")

async def expiration_checker(bot: Bot):
    while True:
        await asyncio.sleep(43200)
        now_ms = int(time.time() * 1000)
        async for session in get_db():
            # بررسی انقضای زمانی — فقط سرویس‌های غیرتست
            time_query = select(ConfigProfile).where(
                ConfigProfile.is_active == True,
                ConfigProfile.is_test == False,
                ConfigProfile.is_unlimited_time == False,
                ConfigProfile.expiry_time < (now_ms + 2 * 24 * 3600 * 1000)  # کمتر از ۲ روز
            )
            exp_configs = (await session.execute(time_query)).scalars().all()
            
            # بررسی اتمام حجم — فقط سرویس‌های غیرتست
            vol_configs = (await session.execute(
                select(ConfigProfile).where(
                    ConfigProfile.is_active == True,
                    ConfigProfile.is_test == False,
                    ConfigProfile.is_unlimited_volume == False,
                    ConfigProfile.volume_gb > 0
                )
            )).scalars().all()
            
        # ارسال هشدار برای کسانی که حجمشان رو به اتمام است
        for c in vol_configs:
            used_gb = c.used_traffic_bytes / (1024**3) if c.used_traffic_bytes else 0
            remaining_gb = c.volume_gb - used_gb
            if 0 <= remaining_gb <= 2 and (not c.last_volume_warning_at or (datetime.utcnow() - c.last_volume_warning_at).days >= 3):
                try:
                    await bot.send_message(
                        c.telegram_id,
                        f"⏳ **هشدار اتمام حجم:**\n"
                        f"📦 کانفیگ: `{c.username}`\n"
                        f"💾 حجم باقی‌مانده: `{remaining_gb:.1f} GB`\n\n"
                        f"🎟 با کد `VIPT10` می‌توانید با **۱۰٪ تخفیف** تمدید کنید!",
                        parse_mode="Markdown"
                    )
                    async for session in get_db():
                        c.last_volume_warning_at = datetime.utcnow()
                        session.add(c)
                        await session.commit()
                except: pass
        
        for c in exp_configs:
            # بررسی وضعیت از پنل
            client_info = await panel_api.get_client_traffic(c.username, c.server_id)
            if not client_info.get("success"):
                # اگر در پنل نیست، حذف یا غیرفعال کن
                async for session in get_db():
                    await session.delete(c)
                    await session.commit()
                await panel_api.delete_client(c.username, c.server_id)
                continue
            
            if not c.last_expiry_warning_at or (datetime.utcnow() - c.last_expiry_warning_at).days >= 3:
                try:
                    await bot.send_message(
                        c.telegram_id,
                        f"⏳ **هشدار انقضا:**\n"
                        f"اعتبار `{c.username}` رو به پایان است.\n\n"
                        f"🎟 با کد `VIPT10` می‌توانید با **۱۰٪ تخفیف** تمدید کنید!",
                        parse_mode="Markdown"
                    )
                    async for session in get_db():
                        c.last_expiry_warning_at = datetime.utcnow()
                        session.add(c)
                        await session.commit()
                except: pass

async def main():
    await init_db()
    await migrate_db()
    bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # افزایش تایم‌اوت برای بهبود اتصال در شبکه ایران
    bot.session.timeout = 60 
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Webhook deleted, starting polling...")
    dp = Dispatcher()
    dp.include_router(content_links.router)
    dp.include_router(start.router)
    dp.include_router(services.router)
    dp.include_router(shop.router)
    dp.include_router(payment.router)
    dp.include_router(test.router)
    dp.include_router(help.router)
    dp.include_router(packages.router)
    dp.include_router(ticket.router)
    dp.include_router(discount.router)
    dp.include_router(ranking.router)
    dp.include_router(renew.router)
    dp.include_router(inbounds.router)
    dp.include_router(config_settings.router)
    dp.include_router(monitoring.router)
    dp.include_router(report.router)
    dp.include_router(admin.router)

    asyncio.create_task(auto_backup_scheduler(bot))
    asyncio.create_task(expiration_checker(bot))
    
    try: await dp.start_polling(bot)
    finally: await panel_api.close()

if __name__ == "__main__":
    asyncio.run(main())
