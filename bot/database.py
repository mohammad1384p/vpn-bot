from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Boolean, select, text
from datetime import datetime

DATABASE_URL = "sqlite+aiosqlite:///./vpn_bot.db"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    phone = Column(String(20), unique=True, nullable=True)
    wallet = Column(Integer, default=0)
    referral_code = Column(String(50), unique=True, nullable=False)
    referred_by = Column(String(50), nullable=True)
    last_test_time = Column(DateTime, nullable=True)
    phone_verified = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    rank = Column(String(20), default="bronze")
    total_spent = Column(Integer, default=0)

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String(100), nullable=True)
    role = Column(String(50), default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    package_id = Column(Integer, nullable=True)
    discount_code = Column(String(50), nullable=True)
    discount_amount = Column(Integer, default=0)
    server_id = Column(Integer, default=1)

class ConfigProfile(Base):
    __tablename__ = "configs"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    sub_link = Column(String(500), nullable=False)
    sub_id = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    expiry_time = Column(BigInteger, nullable=True)
    server_id = Column(Integer, default=1)
    volume_gb = Column(Integer, default=10)
    duration_days = Column(Integer, default=30)
    inbound_ids = Column(String(500), nullable=True)
    is_test = Column(Boolean, default=False)
    used_traffic_bytes = Column(BigInteger, default=0)
    is_unlimited_volume = Column(Boolean, default=False)
    is_unlimited_time = Column(Boolean, default=False)
    group_name = Column(String(100), nullable=True)
    last_volume_warning = Column(BigInteger, default=0)
    last_expiry_warning = Column(BigInteger, default=0)
    last_volume_warning_at = Column(DateTime, nullable=True)
    last_expiry_warning_at = Column(DateTime, nullable=True)

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(50), primary_key=True, nullable=False)
    value = Column(String(2000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Package(Base):
    __tablename__ = "packages"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    volume_gb = Column(Integer, nullable=False, default=0)
    duration_days = Column(Integer, nullable=False, default=0)
    price = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    subject = Column(String(200), nullable=False)
    status = Column(String(20), default="open")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, nullable=False)
    sender_id = Column(BigInteger, nullable=False)
    sender_type = Column(String(20), nullable=False)
    text = Column(String(4000), nullable=True)
    photo_file_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class DiscountCode(Base):
    __tablename__ = "discount_codes"
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    percent = Column(Integer, nullable=False)
    max_uses = Column(Integer, default=0)
    used_count = Column(Integer, default=0)
    min_amount = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_first_purchase = Column(Boolean, default=False)
    is_renewal = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    url = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False)
    inbound_id = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

class ContentLink(Base):
    __tablename__ = "content_links"
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    title = Column(String(200), nullable=True)
    content_type = Column(String(20), nullable=False)
    content_text = Column(String(4000), nullable=True)
    content_file_id = Column(String(255), nullable=True)
    content_caption = Column(String(1000), nullable=True)
    has_ad = Column(Boolean, default=False)
    ad_text = Column(String(2000), nullable=True)
    ad_photo_id = Column(String(255), nullable=True)
    created_by = Column(BigInteger, nullable=False)
    views = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def migrate_db():
    async with engine.begin() as conn:
        migrations = [
            "ALTER TABLE payments ADD COLUMN package_id INTEGER",
            "ALTER TABLE payments ADD COLUMN discount_code TEXT",
            "ALTER TABLE payments ADD COLUMN discount_amount INTEGER DEFAULT 0",
            "ALTER TABLE payments ADD COLUMN server_id INTEGER DEFAULT 1",
            "ALTER TABLE users ADD COLUMN phone_verified BOOLEAN DEFAULT 0",
            "ALTER TABLE users ADD COLUMN rank TEXT DEFAULT 'bronze'",
            "ALTER TABLE users ADD COLUMN total_spent INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT 0",
            "ALTER TABLE configs ADD COLUMN server_id INTEGER DEFAULT 1",
            "ALTER TABLE configs ADD COLUMN volume_gb INTEGER DEFAULT 10",
            "ALTER TABLE configs ADD COLUMN duration_days INTEGER DEFAULT 30",
            "ALTER TABLE configs ADD COLUMN sub_id TEXT",
            "ALTER TABLE configs ADD COLUMN inbound_ids TEXT",
            "ALTER TABLE configs ADD COLUMN is_test BOOLEAN DEFAULT 0",
            "ALTER TABLE configs ADD COLUMN used_traffic_bytes INTEGER DEFAULT 0",
            "ALTER TABLE configs ADD COLUMN is_unlimited_volume BOOLEAN DEFAULT 0",
            "ALTER TABLE configs ADD COLUMN is_unlimited_time BOOLEAN DEFAULT 0",
            "ALTER TABLE configs ADD COLUMN group_name TEXT",
            "ALTER TABLE discount_codes ADD COLUMN is_first_purchase BOOLEAN DEFAULT 0",
            "ALTER TABLE discount_codes ADD COLUMN is_renewal BOOLEAN DEFAULT 0",
            "ALTER TABLE configs ADD COLUMN last_volume_warning_at DATETIME",
            "ALTER TABLE configs ADD COLUMN last_expiry_warning_at DATETIME",
        ]
        for sql in migrations:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def get_setting(session, key: str, default: str = "") -> str:
    result = await session.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else default

async def set_setting(session, key: str, value: str):
    result = await session.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        session.add(Setting(key=key, value=value))
    await session.commit()

async def get_cfg(key: str, default: str = "") -> str:
    async with AsyncSessionLocal() as session:
        return await get_setting(session, key, default)

async def get_channel_ids() -> list:
    raw = await get_cfg("channel_ids", "")
    if not raw: return []
    try:
        return [int(cid.strip()) for cid in raw.split(",") if cid.strip()]
    except:
        return []
