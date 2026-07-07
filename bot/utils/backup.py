import shutil
from bot.config import Config
from bot.database import engine, init_db

async def create_backup():
    await engine.dispose()
    shutil.copy(Config.DB_PATH, Config.BACKUP_PATH)
    return Config.BACKUP_PATH

async def restore_backup(file_path):
    await engine.dispose()
    shutil.copy(file_path, Config.DB_PATH)
    await init_db()
