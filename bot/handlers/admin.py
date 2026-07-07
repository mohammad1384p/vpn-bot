from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func, and_, delete
from bot.database import get_db, User, Payment, ConfigProfile, Package, DiscountCode, Ticket, Server, Admin, get_setting, set_setting
from bot.utils import backup as backup_util
from bot.config import Config as AppConfig
from bot.panel_api import panel_api
from bot.handlers.inbounds import get_selected_inbound_ids
from bot.auth import is_admin, get_admin_info
from bot.utils.helpers import send_config_package
import asyncio, time, re, logging
from datetime import datetime, timedelta

router = Router()

class AdminState(StatesGroup):
    waiting_for_new_value = State()
    waiting_for_balance_amount = State()
    waiting_for_pkg_name = State()
    waiting_for_pkg_volume = State()
    waiting_for_pkg_duration = State()
    waiting_for_pkg_price = State()
    waiting_for_discount_code = State()
    waiting_for_discount_percent = State()
    waiting_for_discount_max = State()
    waiting_for_discount_min = State()
    waiting_for_discount_type = State()
    waiting_for_discount_days = State()
    waiting_for_admin_id = State()
    waiting_for_admin_name = State()
    waiting_for_admin_role = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

ADMIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⚙️ تنظیمات اولیه"), KeyboardButton(text="🖥 مانیتورینگ")],
        [KeyboardButton(text="💰 مالی"), KeyboardButton(text="📦 بسته‌ها")],
        [KeyboardButton(text="🎟 تخفیف‌ها"), KeyboardButton(text="🎫 تیکت‌ها")],
        [KeyboardButton(text="📢 لینک‌های محتوا"), KeyboardButton(text="📊 گزارش‌ها")],
        [KeyboardButton(text="👥 کاربران"), KeyboardButton(text="👮 ادمین‌ها")],
        [KeyboardButton(text="📢 همگانی"), KeyboardButton(text="🗳 دیتابیس")]
    ],
    resize_keyboard=True
)

def format_phone(phone: str) -> str:
    if not phone: return "❌"
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 12 and digits.startswith('98'): return f"+{digits[:2]} {digits[2:5]} {digits[5:8]} {digits[8:]}"
    if len(digits) == 11 and digits.startswith('0'): return f"+98 {digits[1:4]} {digits[4:7]} {digits[7:]}"
    return phone

async def get_user_services_text(session, uid):
    active_configs_count = (await session.execute(select(func.count(ConfigProfile.id)).where(
        ConfigProfile.telegram_id == uid, ConfigProfile.is_active == True, ConfigProfile.is_test == False
    ))).scalar() or 0
    active_configs_res = await session.execute(
        select(ConfigProfile).where(
            ConfigProfile.telegram_id == uid, ConfigProfile.is_active == True, ConfigProfile.is_test == False
        ).order_by(ConfigProfile.id.desc()).limit(5)
    )
    active_configs = active_configs_res.scalars().all()
    services_text = "\n📦 **سرویس‌های فعال:**\n"
    if active_configs:
        for c in active_configs:
            vol = "♾️" if c.is_unlimited_volume else f"{c.volume_gb}GB"
            services_text += f"├ 🔗 `{c.username}` | {vol}\n"
        if active_configs_count > 5: services_text += f"└ ... و {active_configs_count - 5} سرویس دیگر\n"
    else: services_text += "└ ⚠️ سرویس فعالی ندارد\n"
    return services_text

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not await is_admin(message.from_user.id): return await message.answer("❌ دسترسی ندارید.")
    admin_info = await get_admin_info(message.from_user.id)
    is_super = admin_info.get("is_super", False)
    async for session in get_db():
        panel_url = await get_setting(session, "panel_url", "")
        panel_key = await get_setting(session, "panel_api_key", "")
        server_count = (await session.execute(select(Server))).scalar()
    role_text = "👑 Super Admin" if is_super else f"👮 {admin_info.get('name', 'Admin')}"
    if not panel_url or not panel_key or server_count == 0:
        await message.answer(f"👋 **{role_text}**\n⚠️ **تنظیمات اولیه تکمیل نشده.**\n**⚙️ تنظیمات اولیه** را بزنید.", reply_markup=ADMIN_MENU, parse_mode="Markdown")
    else:
        await message.answer(f"🛠 **{role_text}**\nپنل مدیریت:", reply_markup=ADMIN_MENU, parse_mode="Markdown")

@router.message(Command("search_user"))
async def cmd_search_user(message: Message):
    if not await is_admin(message.from_user.id): return
    try:
        parts = message.text.split()
        if len(parts) < 2: return await message.answer("❌ فرمت: `/search_user [آیدی عددی]`", parse_mode="Markdown")
        uid = int(parts[1])
        async for session in get_db():
            user = (await session.execute(select(User).where(User.telegram_id == uid))).scalar_one_or_none()
        if not user: return await message.answer(f"❌ کاربری با آیدی `{uid}` یافت نشد.", parse_mode="Markdown")
        async for session in get_db():
            total_configs = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.telegram_id == uid))).scalar() or 0
            active_configs = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.telegram_id == uid, ConfigProfile.is_active == True, ConfigProfile.is_test == False))).scalar() or 0
            test_configs = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.telegram_id == uid, ConfigProfile.is_test == True))).scalar() or 0
            total_payments = (await session.execute(select(func.sum(Payment.amount)).where(Payment.telegram_id == uid, Payment.status == "approved"))).scalar() or 0
            payments_count = (await session.execute(select(func.count(Payment.id)).where(Payment.telegram_id == uid, Payment.status == "approved"))).scalar() or 0
            refs_count = (await session.execute(select(func.count(User.id)).where(User.referred_by == user.referral_code))).scalar() or 0
            tickets_count = (await session.execute(select(func.count(Ticket.id)).where(Ticket.telegram_id == uid))).scalar() or 0
        phone_display = format_phone(user.phone)
        last_test = "هرگز"
        if user.last_test_time: last_test = user.last_test_time.strftime("%Y-%m-%d %H:%M")
        verified_emoji = "✅" if user.phone_verified else "❌"
        text = (
            f"👤 **جزئیات کاربر (جستجو)**\n🆔 `{uid}`\n📞 `{phone_display}` {verified_emoji}\n"
            f"👛 `{user.wallet:,}` T\n🏆 `{user.rank}`\n💰 مجموع: `{user.total_spent:,}` T\n"
            f"💳 پرداخت: `{payments_count}` عدد (`{total_payments:,}` T)\n"
            f"📦 **سرویس‌ها:**\n├ ✅ فعال: `{active_configs}`\n├ 🧪 تست: `{test_configs}`\n└ 📊 کل: `{total_configs}`\n"
            f"👥 زیرمجموعه: `{refs_count}`\n🎟 کد معرف: `{user.referral_code}`\n🎫 تیکت: `{tickets_count}`\n🧪 آخرین تست: `{last_test}`"
        )
        text += await get_user_services_text(session, uid)
        verify_text = "❌ لغو تایید" if user.phone_verified else "✅ تایید دستی"
        block_text = "🔓 آنبلاک" if user.is_blocked else "🚫 بلاک"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 افزودن", callback_data=f"admin_add_balance:{uid}"), InlineKeyboardButton(text="💸 کسر", callback_data=f"admin_sub_balance:{uid}")],
            [InlineKeyboardButton(text="🔄 ریست تست", callback_data=f"admin_reset_test:{uid}"), InlineKeyboardButton(text=verify_text, callback_data=f"admin_toggle_verify:{uid}")],
            [InlineKeyboardButton(text=block_text, callback_data=f"admin_toggle_block:{uid}")]
        ])
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    except ValueError: await message.answer("❌ آیدی عددی نامعتبر است.")
    except Exception as e: await message.answer(f"❌ خطا: {e}")

@router.message(Command("sendmsg"))
async def cmd_sendmsg(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id): return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3: return await message.answer("❌ فرمت: `/sendmsg [آیدی عددی] [متن پیام]`", parse_mode="Markdown")
        uid = int(parts[1])
        text = parts[2]
        try:
            await bot.send_message(uid, text, parse_mode="Markdown")
            await message.answer(f"✅ پیام با موفقیت به کاربر `{uid}` ارسال شد.", parse_mode="Markdown")
        except Exception as e: await message.answer(f"❌ خطا در ارسال: {e}\nممکن است کاربر ربات را مسدود کرده باشد یا آیدی اشتباه باشد.")
    except ValueError: await message.answer("❌ آیدی عددی نامعتبر است.")
    except Exception as e: await message.answer(f"❌ خطا: {e}")

@router.message(F.text == "👮 ادمین‌ها")
async def admins_menu(message: Message):
    if not await is_admin(message.from_user.id): return
    admin_info = await get_admin_info(message.from_user.id)
    is_super = admin_info.get("is_super", False)
    async for session in get_db():
        result = await session.execute(select(Admin).order_by(Admin.created_at.desc()))
        admins = result.scalars().all()
    text = f"👮 **لیست ادمین‌ها:**\n👑 **Super Admin:** `{AppConfig.ADMIN_ID}`\n"
    if admins:
        for a in admins:
            created = a.created_at.strftime("%Y-%m-%d") if a.created_at else "?"
            text += f"👮 `{a.telegram_id}` | {a.name or 'بدون نام'} | {a.role}\n"
    else: text += "_ادمین دیگری وجود ندارد._\n"
    kb_buttons = []
    if is_super: kb_buttons.append([InlineKeyboardButton(text="➕ افزودن ادمین", callback_data="add_admin_start")])
    for a in admins: kb_buttons.append([InlineKeyboardButton(text=f"🗑 {a.name or a.telegram_id}", callback_data=f"del_admin:{a.telegram_id}")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.callback_query(F.data == "add_admin_start")
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    admin_info = await get_admin_info(callback.from_user.id)
    if not admin_info.get("is_super"): return await callback.answer("❌ فقط Super Admin", show_alert=True)
    await callback.message.answer("👤 آیدی عددی کاربر:")
    await state.set_state(AdminState.waiting_for_admin_id)

@router.message(AdminState.waiting_for_admin_id, F.text)
async def get_admin_id(message: Message, state: FSMContext):
    try: admin_id = int(message.text.strip())
    except ValueError: return await message.answer("❌ آیدی عددی معتبر.")
    if admin_id == AppConfig.ADMIN_ID: return await message.answer("❌ Super Admin است.")
    async for session in get_db():
        existing = (await session.execute(select(Admin).where(Admin.telegram_id == admin_id))).scalar_one_or_none()
    if existing: return await message.answer("❌ قبلاً ادمین است.")
    await state.update_data(new_admin_id=admin_id)
    await message.answer("📝 نام ادمین:")
    await state.set_state(AdminState.waiting_for_admin_name)

@router.message(AdminState.waiting_for_admin_name, F.text)
async def get_admin_name(message: Message, state: FSMContext):
    name = message.text.strip()[:100]
    await state.update_data(new_admin_name=name)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👮 ادمین", callback_data="admin_role:admin")],
        [InlineKeyboardButton(text="🛠 پشتیبانی", callback_data="admin_role:support")],
        [InlineKeyboardButton(text="💼 مدیر", callback_data="admin_role:manager")],
    ])
    await message.answer("🎯 نقش:", reply_markup=kb)
    await state.set_state(AdminState.waiting_for_admin_role)

@router.callback_query(F.data.startswith("admin_role:"))
async def save_admin_with_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split(":")[1]
    data = await state.get_data()
    admin_id = data["new_admin_id"]
    name = data["new_admin_name"]
    async for session in get_db():
        new_admin = Admin(telegram_id=admin_id, name=name, role=role)
        session.add(new_admin)
        await session.commit()
    await state.clear()
    await callback.message.answer(f"✅ **ادمین اضافه شد!**\n👤 `{admin_id}`\n📝 {name}\n🎯 {role}", parse_mode="Markdown")
    try: await callback.bot.send_message(admin_id, f"🎉 شما به عنوان ادمین اضافه شدید!\n🎯 نقش: {role}\n`/admin`", parse_mode="Markdown")
    except: pass

@router.callback_query(F.data.startswith("del_admin:"))
async def del_admin(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    admin_info = await get_admin_info(callback.from_user.id)
    if not admin_info.get("is_super"): return await callback.answer("❌ فقط Super Admin", show_alert=True)
    admin_id = int(callback.data.split(":")[1])
    async for session in get_db():
        await session.execute(delete(Admin).where(Admin.telegram_id == admin_id))
        await session.commit()
    await callback.answer(f"🗑 حذف شد", show_alert=True)
    class FakeMsg:
        def __init__(self, cb): self.from_user = cb.from_user
        async def answer(self, *a, **k): return await callback.message.answer(*a, **k)
    await admins_menu(FakeMsg(callback))

@router.message(Command("addadmin"))
async def cmd_add_admin(message: Message):
    if not await is_admin(message.from_user.id): return
    admin_info = await get_admin_info(message.from_user.id)
    if not admin_info.get("is_super"): return await message.answer("❌ فقط Super Admin")
    parts = message.text.split()
    if len(parts) < 4: return await message.answer("❌ فرمت: `/addadmin [id] [name] [role]`\nمثال: `/addadmin 123456789 Ali admin`", parse_mode="Markdown")
    try:
        admin_id = int(parts[1])
        name = parts[2]
        role = parts[3].lower()
        if role not in ["admin", "support", "manager"]: role = "admin"
        if admin_id == AppConfig.ADMIN_ID: return await message.answer("❌ Super Admin است.")
        async for session in get_db():
            existing = (await session.execute(select(Admin).where(Admin.telegram_id == admin_id))).scalar_one_or_none()
        if existing: return await message.answer("❌ قبلاً ادمین است.")
        async for session in get_db():
            new_admin = Admin(telegram_id=admin_id, name=name, role=role)
            session.add(new_admin)
            await session.commit()
        await message.answer(f"✅ **ادمین اضافه شد!**\n👤 `{admin_id}`\n📝 {name}\n🎯 {role}", parse_mode="Markdown")
        try: await message.bot.send_message(admin_id, f"🎉 شما به عنوان ادمین اضافه شدید!\n🎯 نقش: {role}\n`/admin`", parse_mode="Markdown")
        except: pass
    except Exception as e: await message.answer(f"❌ خطا: {e}")

@router.callback_query(F.data.startswith("user_detail:"))
async def show_user_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    uid = int(callback.data.split(":")[1])
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == uid))).scalar_one_or_none()
    if not user: return await callback.answer("❌ یافت نشد", show_alert=True)
    async for session in get_db():
        total_configs = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.telegram_id == uid))).scalar() or 0
        active_configs = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.telegram_id == uid, ConfigProfile.is_active == True, ConfigProfile.is_test == False))).scalar() or 0
        test_configs = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.telegram_id == uid, ConfigProfile.is_test == True))).scalar() or 0
        total_payments = (await session.execute(select(func.sum(Payment.amount)).where(Payment.telegram_id == uid, Payment.status == "approved"))).scalar() or 0
        payments_count = (await session.execute(select(func.count(Payment.id)).where(Payment.telegram_id == uid, Payment.status == "approved"))).scalar() or 0
        refs_count = (await session.execute(select(func.count(User.id)).where(User.referred_by == user.referral_code))).scalar() or 0
        tickets_count = (await session.execute(select(func.count(Ticket.id)).where(Ticket.telegram_id == uid))).scalar() or 0
    phone_display = format_phone(user.phone)
    last_test = "هرگز"
    if user.last_test_time: last_test = user.last_test_time.strftime("%Y-%m-%d %H:%M")
    verified_emoji = "✅" if user.phone_verified else "❌"
    text = (
        f"👤 **جزئیات کاربر**\n🆔 `{uid}`\n📞 `{phone_display}` {verified_emoji}\n"
        f"👛 `{user.wallet:,}` T\n🏆 `{user.rank}`\n💰 مجموع: `{user.total_spent:,}` T\n"
        f"💳 پرداخت: `{payments_count}` عدد (`{total_payments:,}` T)\n"
        f"📦 **سرویس‌ها:**\n├ ✅ فعال: `{active_configs}`\n├ 🧪 تست: `{test_configs}`\n└ 📊 کل: `{total_configs}`\n"
        f"👥 زیرمجموعه: `{refs_count}`\n🎟 کد معرف: `{user.referral_code}`\n🎫 تیکت: `{tickets_count}`\n🧪 آخرین تست: `{last_test}`"
    )
    text += await get_user_services_text(session, uid)
    verify_text = "❌ لغو تایید" if user.phone_verified else "✅ تایید دستی"
    block_text = "🔓 آنبلاک" if user.is_blocked else "🚫 بلاک"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 افزودن", callback_data=f"admin_add_balance:{uid}"), InlineKeyboardButton(text="💸 کسر", callback_data=f"admin_sub_balance:{uid}")],
        [InlineKeyboardButton(text="🔄 ریست تست", callback_data=f"admin_reset_test:{uid}"), InlineKeyboardButton(text=verify_text, callback_data=f"admin_toggle_verify:{uid}")],
        [InlineKeyboardButton(text=block_text, callback_data=f"admin_toggle_block:{uid}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="user_list:1")]
    ])
    try: await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception: await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_add_balance:"))
async def quick_add_balance(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    uid = int(callback.data.split(":")[1])
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == uid))).scalar_one_or_none()
    if not user: return await callback.answer("❌ یافت نشد", show_alert=True)
    current = user.wallet
    await state.update_data(balance_user_id=uid, balance_action="add")
    await callback.message.answer(f"💰 **افزودن موجودی**\n👤 `{uid}`\n💰 فعلی: `{current:,}` T\nمبلغ را وارد کنید:", parse_mode="Markdown")
    await state.set_state(AdminState.waiting_for_balance_amount)

@router.callback_query(F.data.startswith("admin_sub_balance:"))
async def quick_sub_balance(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    uid = int(callback.data.split(":")[1])
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == uid))).scalar_one_or_none()
    if not user: return await callback.answer("❌ یافت نشد", show_alert=True)
    current = user.wallet
    await state.update_data(balance_user_id=uid, balance_action="sub")
    await callback.message.answer(f"💸 **کسر موجودی**\n👤 `{uid}`\n💰 فعلی: `{current:,}` T\nمبلغ را وارد کنید:", parse_mode="Markdown")
    await state.set_state(AdminState.waiting_for_balance_amount)

@router.message(AdminState.waiting_for_balance_amount, F.text)
async def process_balance_amount(message: Message, state: FSMContext, bot: Bot):
    if not await is_admin(message.from_user.id): return
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ لغو شد", reply_markup=ADMIN_MENU)
        return
    try: amount = int(message.text.strip().replace(",", "").replace(" ", ""))
    except ValueError: return await message.answer("❌ فقط عدد.")
    if amount <= 0: return await message.answer("❌ بزرگتر از صفر.")
    if amount > 100_000_000: return await message.answer("❌ حداکثر 100 میلیون.")
    data = await state.get_data()
    uid = data["balance_user_id"]
    action = data["balance_action"]
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == uid))).scalar_one_or_none()
    if not user:
        await state.clear()
        return await message.answer("❌ کاربر یافت نشد.", reply_markup=ADMIN_MENU)
    if action == "add":
        async for session in get_db():
            user.wallet += amount
            await session.commit()
            new_balance = user.wallet
        await message.answer(f"✅ **موفق!**\n💰 `{amount:,}` T اضافه شد.\n👛 جدید: `{new_balance:,}` T", reply_markup=ADMIN_MENU, parse_mode="Markdown")
        try: await bot.send_message(uid, f"💰 **شارژ کیف پول**\n`{amount:,}` T توسط پشتیبانی اضافه شد.\n👛 `{new_balance:,}` T", parse_mode="Markdown")
        except Exception: pass
    else:
        if user.wallet < amount:
            await state.clear()
            return await message.answer(f"❌ **ناموفق!**\nموجودی (`{user.wallet:,}` T) کمتر از درخواستی (`{amount:,}` T).", reply_markup=ADMIN_MENU, parse_mode="Markdown")
        async for session in get_db():
            user.wallet -= amount
            await session.commit()
            new_balance = user.wallet
        await message.answer(f"✅ **موفق!**\n💸 `{amount:,}` T کسر شد.\n👛 جدید: `{new_balance:,}` T", reply_markup=ADMIN_MENU, parse_mode="Markdown")
        try: await bot.send_message(uid, f"💸 **کسر از کیف پول**\n`{amount:,}` T کسر شد.\n👛 `{new_balance:,}` T", parse_mode="Markdown")
        except Exception: pass
    await state.clear()

@router.callback_query(F.data.startswith("admin_reset_test:"))
async def quick_reset_test(callback: CallbackQuery, bot: Bot):
    if not await is_admin(callback.from_user.id): return
    uid = int(callback.data.split(":")[1])
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == uid))).scalar_one_or_none()
        if user:
            user.last_test_time = None
            await session.commit()
    await callback.answer("✅ ریست شد")
    try: await bot.send_message(uid, "🔄 محدودیت تست ریست شد.")
    except: pass
    await show_user_detail(callback)

@router.callback_query(F.data.startswith("admin_toggle_verify:"))
async def toggle_verify(callback: CallbackQuery, bot: Bot):
    if not await is_admin(callback.from_user.id): return
    uid = int(callback.data.split(":")[1])
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == uid))).scalar_one_or_none()
        if user:
            user.phone_verified = not user.phone_verified
            await session.commit()
            new_status = "تایید ✅" if user.phone_verified else "لغو ❌"
    await callback.answer(f"✅ {new_status}")
    try:
        status_text = "**تایید** شد." if user.phone_verified else "تایید **لغو** شد."
        await bot.send_message(uid, f"🔐 {status_text}", parse_mode="Markdown")
    except: pass
    await show_user_detail(callback)

@router.callback_query(F.data.startswith("admin_toggle_block:"))
async def admin_toggle_block(callback: CallbackQuery, bot: Bot):
    if not await is_admin(callback.from_user.id): return
    uid = int(callback.data.split(":")[1])
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == uid))).scalar_one_or_none()
        if user:
            user.is_blocked = not user.is_blocked
            await session.commit()
            new_status = "بلاکشده 🚫" if user.is_blocked else "رفع بلاک ✅"
    await callback.answer(f"✅ کاربر {new_status}", show_alert=True)
    try:
        status_text = "**بلاکشده‌اید**." if user.is_blocked else "بلاک شما **رفع شد**."
        await bot.send_message(uid, f"⚠️ {status_text}", parse_mode="Markdown")
    except: pass
    await show_user_detail(callback)

@router.message(F.text == "💰 مالی")
async def admin_financial_quick(message: Message):
    if not await is_admin(message.from_user.id): return
    async for session in get_db():
        card_num = await get_setting(session, "card_number", "")
        card_name = await get_setting(session, "card_name", "")
        referral_reward = await get_setting(session, "referral_reward", "10000")
        free_threshold = await get_setting(session, "free_config_threshold", "50000")
    if card_num: card_display = format_phone(card_num) if len(card_num) > 10 else card_num
    else: card_display = "❌"
    text = (
        f"💰 **تنظیمات مالی:**\n💳 `{card_display}`\n👤 `{card_name or '❌'}`\n"
        f"🎁 پاداش: `{int(referral_reward):,}` T\n🎯 آستانه: `{int(free_threshold):,}` T"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 شماره کارت", callback_data="setup_edit:card_number")],
        [InlineKeyboardButton(text="👤 نام", callback_data="setup_edit:card_name")],
        [InlineKeyboardButton(text="🎁 پاداش", callback_data="setup_edit:referral_reward")],
        [InlineKeyboardButton(text="🎯 آستانه", callback_data="setup_edit:free_config_threshold")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.message(F.text == "📊 گزارش‌ها")
async def admin_reports(message: Message):
    if not await is_admin(message.from_user.id): return
    
    # تنظیم ساعت ایران (UTC+3:30) برای محاسبه دقیق "امروز" و "دیروز"
    iran_offset = timedelta(hours=3, minutes=30)
    now_utc = datetime.utcnow()
    now_iran = now_utc + iran_offset
    
    today_iran_start = now_iran.replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc_start = today_iran_start - iran_offset
    
    yesterday_iran_start = today_iran_start - timedelta(days=1)
    yesterday_utc_start = yesterday_iran_start - iran_offset
    
    week_utc_start = now_utc - timedelta(days=7)
    month_utc_start = now_utc - timedelta(days=30)

    async for session in get_db():
        # --- آمار مالی ---
        today_sum = (await session.execute(select(func.sum(Payment.amount)).where(and_(Payment.status == "approved", Payment.created_at >= today_utc_start)))).scalar() or 0
        today_count = (await session.execute(select(func.count(Payment.id)).where(and_(Payment.status == "approved", Payment.created_at >= today_utc_start)))).scalar() or 0
        
        yesterday_sum = (await session.execute(select(func.sum(Payment.amount)).where(and_(Payment.status == "approved", Payment.created_at >= yesterday_utc_start, Payment.created_at < today_utc_start)))).scalar() or 0
        yesterday_count = (await session.execute(select(func.count(Payment.id)).where(and_(Payment.status == "approved", Payment.created_at >= yesterday_utc_start, Payment.created_at < today_utc_start)))).scalar() or 0
        
        week_sum = (await session.execute(select(func.sum(Payment.amount)).where(and_(Payment.status == "approved", Payment.created_at >= week_utc_start)))).scalar() or 0
        month_sum = (await session.execute(select(func.sum(Payment.amount)).where(and_(Payment.status == "approved", Payment.created_at >= month_utc_start)))).scalar() or 0
        total_sum = (await session.execute(select(func.sum(Payment.amount)).where(Payment.status == "approved"))).scalar() or 0
        
        pending_count = (await session.execute(select(func.count(Payment.id)).where(Payment.status == "pending"))).scalar() or 0

        # --- آمار کاربران ---
        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
        verified_users = (await session.execute(select(func.count(User.id)).where(User.phone_verified == True))).scalar() or 0
        total_referrals = (await session.execute(select(func.count(User.id)).where(User.referred_by != None, User.referred_by != ""))).scalar() or 0

        # --- آمار سرویس‌ها ---
        total_configs = (await session.execute(select(func.count(ConfigProfile.id)))).scalar() or 0
        
        # تفکیک سرویس‌های فعال
        active_paid_configs = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.is_active == True, ConfigProfile.is_test == False, ~ConfigProfile.username.like('free_%')))).scalar() or 0
        active_free_configs = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.is_active == True, ConfigProfile.username.like('free_%')))).scalar() or 0
        active_test_configs = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.is_active == True, ConfigProfile.is_test == True))).scalar() or 0
        
        expired_configs = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.is_active == False))).scalar() or 0
        
        # آمار کل سرویس‌ها بر اساس نوع
        free_configs_count = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.username.like('free_%')))).scalar() or 0
        test_configs_count = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.is_test == True))).scalar() or 0
        paid_configs_count = (await session.execute(select(func.count(ConfigProfile.id)).where(ConfigProfile.is_test == False, ~ConfigProfile.username.like('free_%')))).scalar() or 0

        # --- آمار تیکت‌ها ---
        open_tickets = (await session.execute(select(func.count(Ticket.id)).where(Ticket.status == "open"))).scalar() or 0
        replied_tickets = (await session.execute(select(func.count(Ticket.id)).where(Ticket.status == "admin_replied"))).scalar() or 0

        # --- قالب‌بندی و خروجی ---
        def fmt(val): return f"{val:,}" if val else "0"
        
        text = (
            f"📊 **گزارش جامع و دقیق سیستم**\n"
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
            f"├ ✅ **تایید شده (شماره):** `{verified_users}`\n"
            f"└ 👥 **کل زیرمجموعه‌ها:** `{total_referrals}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 **آمار سرویس‌ها و کانفیگ‌ها:**\n"
            f"├ 🟢 **فعال (خریداری شده):** `{active_paid_configs}`\n"
            f"├ 🎁 **فعال (رایگان):** `{active_free_configs}`\n"
            f"├ 🧪 **فعال (تست):** `{active_test_configs}`\n"
            f"├ ⛔ **منقضی شده:** `{expired_configs}`\n"
            f"├ 🛒 **کل خریداری شده:** `{paid_configs_count}`\n"
            f"├ 🎁 **کل رایگان:** `{free_configs_count}`\n"
            f"├ 🧪 **کل تست:** `{test_configs_count}`\n"
            f"└ 📊 **کل سرویس‌ها:** `{total_configs}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎫 **آمار تیکت‌ها:**\n"
            f"├ 🟢 **باز (در انتظار پاسخ):** `{open_tickets}`\n"
            f"└ 🟡 **پاسخ داده شده:** `{replied_tickets}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
        ])
        
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
@router.message(F.text == "🎟 تخفیف‌ها")
async def admin_discounts(message: Message):
    if not await is_admin(message.from_user.id): return
    async for session in get_db():
        result = await session.execute(select(DiscountCode).order_by(DiscountCode.created_at.desc()))
        discounts = result.scalars().all()
    text = "🎟 **کدهای تخفیف:**\n" if discounts else "🎟 کدی تعریف نشده."
    kb_buttons = []
    for dc in discounts:
        status = "✅" if dc.is_active else "⛔"
        text += f"🎫 `{dc.code}` | {dc.percent}% | {dc.used_count}/{dc.max_uses if dc.max_uses > 0 else '∞'}\n"
        kb_buttons.append([InlineKeyboardButton(text=f"{status} {dc.code}", callback_data=f"manage_disc:{dc.id}")])
    kb_buttons.append([InlineKeyboardButton(text="➕ افزودن کد", callback_data="add_discount")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("manage_disc:"))
async def manage_discount(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    disc_id = int(callback.data.split(":")[1])
    async for session in get_db():
        dc = (await session.execute(select(DiscountCode).where(DiscountCode.id == disc_id))).scalar_one_or_none()
    if not dc: return await callback.answer("❌ یافت نشد")
    status = "✅ فعال" if dc.is_active else "⛔ غیرفعال"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛔ غیرفعال" if dc.is_active else "✅ فعال", callback_data=f"toggle_disc:{dc.id}")],
        [InlineKeyboardButton(text="🗑 حذف", callback_data=f"del_disc:{dc.id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_discounts")],
    ])
    await callback.message.edit_text(f"🎟 **{dc.code}**\n📊 وضعیت: {status}\n📉 درصد: {dc.percent}%\n🔢 استفاده: {dc.used_count}/{dc.max_uses}", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("toggle_disc:"))
async def toggle_discount_status(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    disc_id = int(callback.data.split(":")[1])
    async for session in get_db():
        dc = (await session.execute(select(DiscountCode).where(DiscountCode.id == disc_id))).scalar_one_or_none()
        if dc:
            dc.is_active = not dc.is_active
            await session.commit()
            status = "فعال ✅" if dc.is_active else "غیرفعال ⛔"
            await callback.answer(f"✅ وضعیت به {status} تغییر کرد", show_alert=True)
        else:
            await callback.answer("❌ یافت نشد", show_alert=True)
    await manage_discount(callback)

@router.callback_query(F.data.startswith("del_disc:"))
async def delete_discount(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    disc_id = int(callback.data.split(":")[1])
    async for session in get_db():
        dc = (await session.execute(select(DiscountCode).where(DiscountCode.id == disc_id))).scalar_one_or_none()
        if dc:
            code_name = dc.code
            await session.delete(dc)
            await session.commit()
            await callback.answer(f"🗑 کد {code_name} حذف شد", show_alert=True)
        else:
            await callback.answer("❌ یافت نشد", show_alert=True)
    class FakeMsg:
        def __init__(self, cb): self.from_user = cb.from_user
        async def answer(self, *a, **k): return await callback.message.answer(*a, **k)
    await admin_discounts(FakeMsg(callback))

@router.callback_query(F.data == "add_discount")
async def back_to_discounts(callback: CallbackQuery):
    class FakeMsg:
        def __init__(self, cb): self.from_user = cb.from_user
        async def answer(self, *a, **k): return await callback.message.answer(*a, **k)
    await admin_discounts(FakeMsg(callback))

@router.callback_query(F.data == "add_discount")
async def start_add_discount(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("📝 کد تخفیف:")
    await state.set_state(AdminState.waiting_for_discount_code)

@router.message(AdminState.waiting_for_discount_code)
async def get_discount_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip().upper())
    await message.answer("💯 درصد:")
    await state.set_state(AdminState.waiting_for_discount_percent)

@router.message(AdminState.waiting_for_discount_percent, F.text.isdigit())
async def get_discount_percent(message: Message, state: FSMContext):
    await state.update_data(percent=int(message.text))
    await message.answer("🔢 حداکثر استفاده (0 = نامحدود):")
    await state.set_state(AdminState.waiting_for_discount_max)

@router.message(AdminState.waiting_for_discount_max, F.text.isdigit())
async def get_discount_max(message: Message, state: FSMContext):
    await state.update_data(max_uses=int(message.text))
    await message.answer("💰 حداقل مبلغ:")
    await state.set_state(AdminState.waiting_for_discount_min)

@router.message(AdminState.waiting_for_discount_min, F.text.isdigit())
async def get_discount_min(message: Message, state: FSMContext):
    await state.update_data(min_amount=int(message.text))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ عمومی", callback_data="disc_type:general")],
        [InlineKeyboardButton(text="2️⃣ فقط خرید اول", callback_data="disc_type:first")],
        [InlineKeyboardButton(text="3️⃣ فقط تمدید", callback_data="disc_type:renew")],
    ])
    await message.answer("🎯 **نوع کد تخفیف:**", reply_markup=kb)
    await state.set_state(AdminState.waiting_for_discount_type)

@router.callback_query(F.data.startswith("disc_type:"))
async def save_discount_type(callback: CallbackQuery, state: FSMContext):
    disc_type = callback.data.split(":")[1]
    await state.update_data(disc_type=disc_type)
    await callback.message.answer("📅 روز اعتبار (0 = نامحدود):")
    await state.set_state(AdminState.waiting_for_discount_days)

@router.message(AdminState.waiting_for_discount_days, F.text.isdigit())
async def save_discount(message: Message, state: FSMContext):
    data = await state.get_data()
    days = int(message.text)
    expires_at = datetime.utcnow() + timedelta(days=days) if days > 0 else None
    is_first = data.get("disc_type") == "first"
    is_renew = data.get("disc_type") == "renew"
    try:
        async for session in get_db():
            existing = (await session.execute(select(DiscountCode).where(DiscountCode.code == data["code"]))).scalar_one_or_none()
            if existing:
                await state.clear()
                return await message.answer(f"❌ **خطا!**\nکد تخفیف `{data['code']}` قبلاً ثبت شده است. لطفاً از کد دیگری استفاده کنید یا کد قبلی را حذف کنید.", parse_mode="Markdown")
                
            dc = DiscountCode(code=data["code"], percent=data["percent"], max_uses=data["max_uses"], min_amount=data["min_amount"], expires_at=expires_at, is_first_purchase=is_first, is_renewal=is_renew)
            session.add(dc)
            await session.commit()
        await state.clear()
        type_text = "عمومی" if data.get("disc_type") == "general" else ("فقط خرید اول" if is_first else "فقط تمدید")
        await message.answer(f"✅ `{data['code']}` ساخته شد!\n🎯 نوع: {type_text}", parse_mode="Markdown")
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ خطایی در ثبت کد رخ داد:\n`{e}`", parse_mode="Markdown")

@router.message(F.text == "📦 بسته‌ها")
async def admin_packages(message: Message):
    if not await is_admin(message.from_user.id): return
    async for session in get_db():
        result = await session.execute(select(Package).order_by(Package.sort_order.asc(), Package.price.asc()))
        packages = result.scalars().all()
    text = "📦 **بسته‌ها:**\n" if packages else "📦 بسته‌ای تعریف نشده."
    for pkg in packages:
        status = "✅" if pkg.is_active else "⛔"
        vol = "♾️" if pkg.volume_gb <= 0 else f"{pkg.volume_gb}GB"
        dur = "♾️" if pkg.duration_days <= 0 else f"{pkg.duration_days}d"
        text += f"**{pkg.name}** [{status}]\n└ 📦 {vol} | ⏱ {dur} | 💰 {pkg.price:,}T\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن", callback_data="add_package")],
        [InlineKeyboardButton(text="✏️ ویرایش", callback_data="manage_packages")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "add_package")
async def start_add_package(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("📝 نام بسته:")
    await state.set_state(AdminState.waiting_for_pkg_name)

@router.message(AdminState.waiting_for_pkg_name)
async def get_pkg_name(message: Message, state: FSMContext):
    await state.update_data(pkg_name=message.text.strip())
    await message.answer("📦 حجم (GB) - `0` نامحدود:", parse_mode="Markdown")
    await state.set_state(AdminState.waiting_for_pkg_volume)

@router.message(AdminState.waiting_for_pkg_volume, F.text)
async def get_pkg_volume(message: Message, state: FSMContext):
    try:
        vol = int(message.text.strip())
        if vol < 0: return await message.answer("❌ >= 0")
    except: return await message.answer("❌ فقط عدد")
    await state.update_data(pkg_volume=vol)
    await message.answer("⏱ مدت (روز) - `0` نامحدود:", parse_mode="Markdown")
    await state.set_state(AdminState.waiting_for_pkg_duration)

@router.message(AdminState.waiting_for_pkg_duration, F.text)
async def get_pkg_duration(message: Message, state: FSMContext):
    try:
        dur = int(message.text.strip())
        if dur < 0: return await message.answer("❌ >= 0")
    except: return await message.answer("❌ فقط عدد")
    await state.update_data(pkg_duration=dur)
    await message.answer("💰 قیمت (تومان):")
    await state.set_state(AdminState.waiting_for_pkg_price)

@router.message(AdminState.waiting_for_pkg_price, F.text.isdigit())
async def save_package(message: Message, state: FSMContext):
    data = await state.get_data()
    async for session in get_db():
        pkg = Package(name=data["pkg_name"], volume_gb=data["pkg_volume"], duration_days=data["pkg_duration"], price=int(message.text))
        session.add(pkg)
        await session.commit()
    await state.clear()
    await message.answer(f"✅ **{data['pkg_name']}** ساخته شد!", reply_markup=ADMIN_MENU, parse_mode="Markdown")

@router.callback_query(F.data == "manage_packages")
async def manage_packages_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    async for session in get_db():
        result = await session.execute(select(Package).order_by(Package.id.desc()))
        packages = result.scalars().all()
    kb_buttons = [[InlineKeyboardButton(text=f"{'✅' if pkg.is_active else '⛔'} {pkg.name}", callback_data=f"edit_pkg:{pkg.id}")] for pkg in packages]
    await callback.message.edit_text("✏️ انتخاب بسته:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))

@router.callback_query(F.data.startswith("edit_pkg:"))
async def edit_package_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    pkg_id = int(callback.data.split(":")[1])
    async for session in get_db():
        pkg = (await session.execute(select(Package).where(Package.id == pkg_id))).scalar_one_or_none()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛔" if pkg.is_active else "✅", callback_data=f"toggle_pkg:{pkg.id}")],
        [InlineKeyboardButton(text="🗑", callback_data=f"delete_pkg:{pkg.id}")]
    ])
    await callback.message.edit_text(f"📦 **{pkg.name}**", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("toggle_pkg:"))
async def toggle_package(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    pkg_id = int(callback.data.split(":")[1])
    async for session in get_db():
        pkg = (await session.execute(select(Package).where(Package.id == pkg_id))).scalar_one_or_none()
        if pkg:
            pkg.is_active = not pkg.is_active
            await session.commit()
    await callback.answer("✅")

@router.callback_query(F.data.startswith("delete_pkg:"))
async def delete_package(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    pkg_id = int(callback.data.split(":")[1])
    async for session in get_db():
        pkg = (await session.execute(select(Package).where(Package.id == pkg_id))).scalar_one_or_none()
        if pkg:
            await session.delete(pkg)
            await session.commit()
    await callback.answer("🗑")

@router.message(F.text == "🗳 دیتابیس")
async def admin_db(message: Message):
    if not await is_admin(message.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 بکاپ", callback_data="db_backup")], [InlineKeyboardButton(text="📤 ریستور", callback_data="db_restore_prompt")]])
    await message.answer("🗳 **دیتابیس:**", reply_markup=kb, parse_mode="Markdown")

@router.message(F.text == "👥 کاربران")
async def admin_users(message: Message):
    if not await is_admin(message.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 لیست", callback_data="user_list:1")]])
    await message.answer("👥 **کاربران:**\n`/verify_user [id] [phone]`\n`/reset_phone [id]`\n`/search_user [id]`", reply_markup=kb, parse_mode="Markdown")

@router.message(F.text == "📢 همگانی")
async def admin_broadcast(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await message.answer("📢 پیام را ارسال کنید (/cancel):\n_این پیام به تمام کاربران (تایید شده و نشده) ارسال می‌شود._", parse_mode="Markdown")
    await state.set_state(BroadcastState.waiting_for_message)

@router.callback_query(F.data == "db_backup")
async def manual_backup(callback: CallbackQuery, bot: Bot):
    if not await is_admin(callback.from_user.id): return
    path = await backup_util.create_backup()
    await bot.send_document(callback.from_user.id, FSInputFile(path), caption="🗳 بکاپ")
    import os; os.remove(path)
    await callback.answer("✅")

@router.callback_query(F.data == "db_restore_prompt")
async def db_restore_prompt(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("⚠️ فایل `.db` را ارسال کنید.")
    await state.update_data(action="restore_db")
    await state.set_state(AdminState.waiting_for_new_value)

@router.message(AdminState.waiting_for_new_value, F.document)
async def process_restore(message: Message, state: FSMContext, bot: Bot):
    if not await is_admin(message.from_user.id): return
    data = await state.get_data()
    if data.get("action") != "restore_db": return
    file = await bot.get_file(message.document.file_id)
    temp = "./temp_restore.db"
    await bot.download_file(file.file_path, temp)
    await backup_util.restore_backup(temp)
    import os; os.remove(temp)
    await state.clear()
    await message.answer("✅ ریستور شد", reply_markup=ADMIN_MENU)

@router.callback_query(F.data.startswith("user_list:"))
async def show_user_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    page = int(callback.data.split(":")[1])
    async for session in get_db():
        users = (await session.execute(select(User).order_by(User.id.desc()).limit(10).offset((page-1)*10))).scalars().all()
        total = (await session.execute(select(func.count(User.id)))).scalar()
    text = f"📋 **کاربران ({page}/{(total+9)//10}):**\n"
    kb_buttons = []
    for u in users:
        verified = "✅" if u.phone_verified else "❌"
        phone_short = format_phone(u.phone).split()[1] if u.phone and " " in format_phone(u.phone) else ("?" if not u.phone else u.phone[-4:])
        text += f"👤 `{u.telegram_id}` | 📞 {phone_short} {verified} | 💰 {u.wallet:,}T\n"
        kb_buttons.append([InlineKeyboardButton(text=f"👤 {u.telegram_id}", callback_data=f"user_detail:{u.telegram_id}")])
    nav = []
    if page > 1: nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"user_list:{page-1}"))
    if page * 10 < total: nav.append(InlineKeyboardButton(text="➡️", callback_data=f"user_list:{page+1}"))
    if nav: kb_buttons.append(nav)
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not await is_admin(message.from_user.id): return
    await state.clear()
    async for session in get_db():
        uids = (await session.execute(select(User.telegram_id))).scalars().all()
    msg = await message.answer("⏳ در حال ارسال پیام همگانی به تمام کاربران (تایید شده و نشده)...")
    success = 0
    failed = 0
    for uid in uids:
        try:
            if message.photo: await bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "")
            else: await bot.send_message(uid, message.text)
            success += 1
        except: failed += 1
        await asyncio.sleep(0.05)
    await msg.edit_text(f"✅ **پیام همگانی ارسال شد.**\n👥 کل کاربران: `{len(uids)}`\n✅ موفق: `{success}`\n❌ مسدود/خطا: `{failed}`", parse_mode="Markdown")

@router.callback_query(F.data.startswith("approve_pay_"))
async def approve_payment(callback: CallbackQuery, bot: Bot):
    if not await is_admin(callback.from_user.id): return
    payment_id = int(callback.data.split("_")[-1])
    async for session in get_db():
        payment = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if not payment or payment.status != "pending": return await callback.answer("قبلاً")
    
    async for session in get_db():
        payment.status = "approved"
        user = (await session.execute(select(User).where(User.telegram_id == payment.telegram_id))).scalar_one_or_none()
        if user:
            user.total_spent += payment.amount
            from bot.handlers.ranking import calculate_rank
            user.rank = calculate_rank(user.total_spent)
            
        volume_gb, duration_hours, pkg_name = 10, 720, "سفارش اختصاصی"
        unlimited_vol, unlimited_dur = False, False
        if payment.package_id:
            pkg = (await session.execute(select(Package).where(Package.id == payment.package_id))).scalar_one_or_none()
            if pkg:
                pkg_name = pkg.name
                if pkg.volume_gb <= 0: unlimited_vol, volume_gb = True, 0
                else: volume_gb = pkg.volume_gb
                if pkg.duration_days <= 0: unlimited_dur, duration_hours = True, 0
                else: duration_hours = pkg.duration_days * 24
        await session.commit()
        
    email = f"user_{user.telegram_id}_{int(time.time())}"
    selected_inbound_ids = await get_selected_inbound_ids()
    res = await panel_api.add_client(
        email=email, total_gb=volume_gb, expiry_hours=duration_hours,
        inbound_ids=selected_inbound_ids if selected_inbound_ids else None,
        unlimited_volume=unlimited_vol, unlimited_time=unlimited_dur
    )
    if res["success"]:
        inbound_ids_str = ",".join(str(x) for x in res.get("inbound_ids", []))
        async for session in get_db():
            session.add(ConfigProfile(
                telegram_id=user.telegram_id, username=email, sub_link=res["sub_link"],
                sub_id=res.get("sub_id"), is_active=True, expiry_time=res.get("expiry_time_ms", 0),
                server_id=res["server_id"], volume_gb=volume_gb,
                duration_days=pkg.duration_days if payment.package_id else (duration_hours // 24 if duration_hours > 0 else 0),
                inbound_ids=inbound_ids_str, is_test=False, is_unlimited_volume=unlimited_vol, is_unlimited_time=unlimited_dur
            ))
            await session.commit()
            
        vol_display = "♾️ نامحدود" if unlimited_vol else f"{volume_gb} GB"
        dur_display = "♾️ نامحدود" if unlimited_dur else f"{pkg.duration_days if payment.package_id else (duration_hours // 24 if duration_hours > 0 else 0)} روز"
        
        await send_config_package(
            bot=bot, user_id=user.telegram_id, sub_link=res['sub_link'],
            username=email, volume_display=vol_display, duration_display=dur_display, is_renew=False
        )
        await callback.message.edit_text(callback.message.text + f"\n✅ تایید | {res.get('inbounds_count', '?')} اینباند")
    else:
        await callback.message.edit_text(callback.message.text + f"\n⚠️ {res['msg']}")

@router.callback_query(F.data.startswith("reject_pay_"))
async def reject_payment(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    payment_id = int(callback.data.split("_")[-1])
    async for session in get_db():
        payment = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
        if payment:
            payment.status = "rejected"
            await session.commit()
    await callback.message.edit_text(callback.message.text + "\n❌ رد")

@router.message(Command("cancel"))
async def cancel_fsm(message: Message, state: FSMContext):
    await state.clear()
    if await is_admin(message.from_user.id): await message.answer("لغو شد", reply_markup=ADMIN_MENU)
    else:
        from bot.handlers.start import MAIN_MENU
        await message.answer("لغو شد", reply_markup=MAIN_MENU)

@router.message(Command("send_config"))
async def cmd_send_config(message: Message):
    if not await is_admin(message.from_user.id): return
    try:
        parts = message.text.split(maxsplit=2)
        uid, link = int(parts[1]), parts[2]
        async for session in get_db():
            session.add(ConfigProfile(
                telegram_id=uid, username=f"manual_{uid}_{int(time.time())}",
                sub_link=link, is_active=True, volume_gb=10, duration_days=30, is_test=False
            ))
            await session.commit()
        try: await message.bot.send_message(uid, f"✅ <code>{link}</code>", parse_mode="HTML")
        except: pass
        await message.answer("✅ ارسال شد")
    except: await message.answer("❌ `/send_config [id] [link]`")
