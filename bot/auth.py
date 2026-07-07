from bot.config import Config
from bot.database import get_db, Admin
from sqlalchemy import select

async def is_admin(user_id: int) -> bool:
    if user_id == Config.ADMIN_ID: return True
    try:
        async for session in get_db():
            result = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
            return result.scalar_one_or_none() is not None
    except: pass
    return False

async def get_admin_info(user_id: int) -> dict:
    if user_id == Config.ADMIN_ID:
        return {"is_super": True, "role": "super_admin", "name": "Super Admin"}
    try:
        async for session in get_db():
            result = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
            admin = result.scalar_one_or_none()
            if admin:
                return {"is_super": False, "role": admin.role, "name": admin.name or f"Admin {user_id}"}
    except: pass
    return None
