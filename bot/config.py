import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
    DB_PATH = "./vpn_bot.db"
    BACKUP_PATH = "./vpn_bot_backup.db"
