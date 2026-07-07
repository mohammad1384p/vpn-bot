from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from bot.database import Server, get_db, get_setting, set_setting
from bot.panel_api import panel_api
from bot.config import Config
from bot.auth import is_admin
import json

router = Router()

class SetupState(StatesGroup):
    waiting_for_panel_url = State()
    waiting_for_panel_api_key = State()
    waiting_for_panel_name = State()
    waiting_for_card_number = State()
    waiting_for_card_name = State()
    waiting_for_channel_ids = State()
    waiting_for_support_username = State()
    waiting_for_referral_reward = State()
    waiting_for_test_volume = State()
    waiting_for_test_duration = State()
    waiting_for_test_cooldown = State()
    waiting_for_free_threshold = State()
    waiting_for_help_android = State()
    waiting_for_help_ios = State()
    waiting_for_help_windows = State()
    waiting_for_sub_link_pattern = State()
    waiting_for_max_test = State()
    waiting_for_bot_username = State()
    waiting_for_free_volume = State()
    waiting_for_free_duration = State()

SETTINGS_SCHEMA = {
    "bot": {"title": "🤖 ربات", "icon": "🤖", "items": {"bot_username": {"label": "نام کاربری ربات", "example": "MyVpnBot", "default": ""}}},
    "panel": {"title": "🌐 اتصال به پنل", "icon": "🌐", "items": {"panel_url": {"label": "آدرس پنل", "example": "https://panel.com:54321/path"}, "panel_api_key": {"label": "API Token", "example": "Bearer token"}}},
    "subscription": {"title": "🔗 لینک ساب", "icon": "🔗", "items": {"sub_link_pattern": {"label": "الگوی لینک ساب", "example": "https://domain.com:2096/sub/{subId}", "default": ""}}},
    "payment": {"title": "💳 پرداخت", "icon": "💳", "items": {"card_number": {"label": "شماره کارت", "example": "6037991234567890"}, "card_name": {"label": "نام صاحب کارت", "example": "علی محمدی"}}},
    "channels": {"title": "📢 کانال‌ها", "icon": "📢", "items": {"channel_ids": {"label": "آیدی کانال‌ها", "example": "-1001234,-1005678"}}},
    "support": {"title": "📞 پشتیبانی", "icon": "📞", "items": {"support_username": {"label": "یوزرنیم", "example": "my_support"}}},
    "business": {"title": "💰 کسب‌وکار", "icon": "💰", "items": {"referral_reward": {"label": "پاداش زیرمجموعه", "example": "10000", "default": "10000"}, "free_config_threshold": {"label": "آستانه رایگان", "example": "50000", "default": "50000"}}},
    "free": {"title": "🎁 کانفیگ رایگان", "icon": "🎁", "items": {"free_config_volume_gb": {"label": "حجم (GB)", "example": "10", "default": "10"}, "free_config_duration_days": {"label": "مدت (روز)", "example": "30", "default": "30"}}},
    "test": {"title": "🧪 تست", "icon": "🧪", "items": {"test_volume_mb": {"label": "حجم تست (MB)", "example": "100", "default": "100"}, "test_duration_hours": {"label": "مدت (ساعت)", "example": "1", "default": "1"}, "test_cooldown_hours": {"label": "کول‌داون (ساعت)", "example": "24", "default": "24"}, "max_test_per_user": {"label": "حداکثر تعداد تست", "example": "3", "default": "1"}}},
    "help": {"title": "🎓 آموزش", "icon": "🎓", "items": {"help_android": {"label": "اندروید", "example": "https://..."}, "help_ios": {"label": "آیفون", "example": "https://..."}, "help_windows": {"label": "ویندوز", "example": "https://..."}}},
}

async def safe_edit_or_send(callback_or_message, text, reply_markup=None, parse_mode=None):
    if isinstance(callback_or_message, CallbackQuery):
        try: await callback_or_message.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except TelegramBadRequest: await callback_or_message.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else: await callback_or_message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)

async def build_setup_wizard_content():
    async for session in get_db():
        panel_url = await get_setting(session, "panel_url", "")
        panel_key = await get_setting(session, "panel_api_key", "")
        card_num = await get_setting(session, "card_number", "")
        card_name = await get_setting(session, "card_name", "")
        channels = await get_setting(session, "channel_ids", "")
        support = await get_setting(session, "support_username", "")
        sub_pattern = await get_setting(session, "sub_link_pattern", "")
        bot_username = await get_setting(session, "bot_username", "")
        server_count = (await session.execute(select(Server))).scalar()
    def status_icon(value, critical=False): return "✅" if value else ("🔴" if critical else "⚪")
    text = (
        f"⚙️ **تنظیمات:**\n"
        f"{status_icon(bot_username, True)} نام ربات: {'✅' if bot_username else '❌'}\n"
        f"{status_icon(panel_url, True)} پنل: {'✅' if panel_url else '❌'}\n"
        f"{status_icon(panel_key, True)} Token: {'✅' if panel_key else '❌'}\n"
        f"🖥 سرور: `{server_count}`\n"
        f"{status_icon(sub_pattern)} ساب: {'✅' if sub_pattern else '⚪'}\n"
        f"{status_icon(card_num)} کارت: {'✅' if card_num else '⚪'}\n"
        f"{status_icon(card_name)} نام: {'✅' if card_name else '⚪'}\n"
        f"{status_icon(channels)} کانال: {'✅' if channels else '⚪'}\n"
        f"{status_icon(support)} پشتیبانی: {'✅' if support else '⚪'}"
    )
    kb_buttons = [
        [InlineKeyboardButton(text="🤖 ربات 🔴", callback_data="setup_section:bot")],
        [InlineKeyboardButton(text="🌐 پنل 🔴", callback_data="setup_section:panel")],
        [InlineKeyboardButton(text="🔗 ساب", callback_data="setup_section:subscription")],
        [InlineKeyboardButton(text="💳 پرداخت", callback_data="setup_section:payment")],
        [InlineKeyboardButton(text="📢 کانال‌ها", callback_data="setup_section:channels")],
        [InlineKeyboardButton(text="📞 پشتیبانی", callback_data="setup_section:support")],
        [InlineKeyboardButton(text="💰 کسب‌وکار", callback_data="setup_section:business")],
        [InlineKeyboardButton(text="🎁 رایگان", callback_data="setup_section:free")],
        [InlineKeyboardButton(text="🧪 تست", callback_data="setup_section:test")],
        [InlineKeyboardButton(text="🎓 آموزش", callback_data="setup_section:help")],
        [InlineKeyboardButton(text="🌍 سرورها", callback_data="setup_servers")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_admin")],
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=kb_buttons)

@router.callback_query(F.data == "setup_wizard")
async def setup_wizard_callback(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    text, kb = await build_setup_wizard_content()
    await safe_edit_or_send(callback, text, kb, "Markdown")

@router.message(F.text == "⚙️ تنظیمات اولیه")
async def setup_wizard_text(message: Message):
    if not await is_admin(message.from_user.id): return
    text, kb = await build_setup_wizard_content()
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("setup_section:"))
async def show_section(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    section_key = callback.data.split(":")[1]
    if section_key == "subscription":
        await show_subscription_section(callback)
        return
    section = SETTINGS_SCHEMA.get(section_key)
    if not section: return
    text = f"{section['icon']} **{section['title']}**\n"
    kb_buttons = []
    async for session in get_db():
        for key, info in section["items"].items():
            current = await get_setting(session, key, info.get("default", ""))
            if current:
                display = current[:30] + "..." if len(current) > 30 else current
                if key in ["panel_api_key"]: display = "***" + display[-4:] if len(display) > 4 else "***"
                status = f"✅ `{display}`"
            else: status = "⚪"
            text += f"**{info['label']}:** {status}\n"
            kb_buttons.append([InlineKeyboardButton(text=f"✏️ {info['label']}", callback_data=f"setup_edit:{key}")])
    kb_buttons.append([InlineKeyboardButton(text="🔙", callback_data="setup_wizard")])
    await safe_edit_or_send(callback, text, InlineKeyboardMarkup(inline_keyboard=kb_buttons), "Markdown")

@router.callback_query(F.data == "setup_section:subscription")
async def show_subscription_section(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    async for session in get_db():
        current = await get_setting(session, "sub_link_pattern", "")
    if current:
        display = current if len(current) < 80 else current[:77] + "..."
        status = f"🎯 **الگو:**\n`{display}`"
    else: status = "🔄 **خودکار**"
    text = f"🔗 **لینک ساب**\n{status}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ پیشرفته", callback_data="setup_subscription_advanced")],
        [InlineKeyboardButton(text="✏️ دستی", callback_data="setup_edit:sub_link_pattern")],
        [InlineKeyboardButton(text="🔙", callback_data="setup_wizard")],
    ])
    await safe_edit_or_send(callback, text, kb, "Markdown")

@router.callback_query(F.data == "setup_subscription_advanced")
async def setup_subscription_advanced(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    async for session in get_db():
        current = await get_setting(session, "sub_link_pattern", "")
    placeholder = "{subId}"
    text = f"🔗 **پیشرفته**\n📌 الگو: `{current or '⚪ خودکار'}`\n💡 `{placeholder}` با Sub ID واقعی جایگزین می‌شود"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 تشخیص خودکار", callback_data="auto_detect_sub")],
        [InlineKeyboardButton(text="👁 نمونه", callback_data="preview_sub_link")],
        [InlineKeyboardButton(text="✏️ الگو", callback_data="setup_edit:sub_link_pattern")],
        [InlineKeyboardButton(text="🗑 حذف", callback_data="clear_sub_pattern")],
        [InlineKeyboardButton(text="🔙", callback_data="setup_section:subscription")],
    ])
    await safe_edit_or_send(callback, text, kb, "Markdown")

@router.callback_query(F.data == "auto_detect_sub")
async def auto_detect_sub_pattern(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    await callback.answer("🔍 در حال خواندن...")
    async for session in get_db():
        result = await session.execute(select(Server).where(Server.is_active == True).order_by(Server.priority.asc()))
        server = result.scalars().first()
    if not server: return await callback.message.answer("❌ سرور فعال وجود ندارد.")
    session, base_url = await panel_api._get_session(server)
    try:
        async with session.post(f"{base_url}/panel/api/setting/all", timeout=15) as resp:
            if resp.status != 200: return await callback.message.answer(f"❌ HTTP {resp.status}")
            data = await resp.json()
            obj = data.get("obj", data) if isinstance(data, dict) else {}
            if isinstance(obj, str):
                try: obj = json.loads(obj)
                except: obj = {}
    except Exception as e: return await callback.message.answer(f"❌ خطا: {e}")
    
    sub_base_uri = obj.get("subBaseUri", "") or obj.get("subURI", "")
    sub_path = (obj.get("subPath", "sub") or "sub").strip('/')
    sub_port = str(obj.get("subPort", "") or "").strip()
    sub_domain = (obj.get("subDomain", "") or "").strip()
    from urllib.parse import urlparse
    parsed_panel = urlparse(server.url)
    protocol = parsed_panel.scheme or "https"
    panel_host = parsed_panel.hostname or "localhost"
    placeholder = "{subId}"
    detected_pattern, source_info = "", ""
    
    if sub_base_uri and sub_base_uri.startswith("http"):
        detected_pattern = sub_base_uri.rstrip('/') + "/" + placeholder
        source_info = "📡 subBaseUri"
    elif sub_domain:
        if sub_domain.startswith("http"):
            host_part = urlparse(sub_domain).netloc or sub_domain
            detected_pattern = f"{protocol}://{host_part}/{sub_path}/" + placeholder
        else: detected_pattern = f"{protocol}://{sub_domain}/{sub_path}/" + placeholder
        source_info = "📡 subDomain"
    elif sub_port:
        detected_pattern = f"{protocol}://{panel_host}:{sub_port}/{sub_path}/" + placeholder
        source_info = f"📡 subPort ({sub_port})"
    else:
        detected_pattern = f"{protocol}://{panel_host}/{sub_path}/" + placeholder
        source_info = "📡 subPath"
        
    async for session in get_db(): await set_setting(session, "sub_link_pattern", detected_pattern)
    sample_sub_id = "d8bf817e21634036"
    sample_link = detected_pattern.replace(placeholder, sample_sub_id)
    await callback.message.answer(f"✅ **تشخیص داده شد!**\n{source_info}\n📌 الگو:\n`{detected_pattern}`\n🔗 نمونه:\n`{sample_link}`", parse_mode="Markdown")

@router.callback_query(F.data == "preview_sub_link")
async def preview_sub_link(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    async for session in get_db():
        result = await session.execute(select(Server).where(Server.is_active == True).order_by(Server.priority.asc()))
        server = result.scalars().first()
    if not server: return await callback.message.answer("❌ سرور فعال وجود ندارد.")
    sample_sub_id = "d8bf817e21634036"
    sample_link = await panel_api.get_sub_link(sample_sub_id, server)
    base_url = await panel_api.get_sub_base_url(server)
    async for session in get_db():
        current_pattern = await get_setting(session, "sub_link_pattern", "")
    mode = "🎯 سفارشی" if current_pattern else "🔄 خودکار"
    await callback.message.answer(f"👁 **پیش‌نمایش**\n{mode}\n📌 Base:\n`{base_url}`\n🔗 نمونه:\n`{sample_link}`", parse_mode="Markdown")

@router.callback_query(F.data == "clear_sub_pattern")
async def clear_sub_pattern(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    async for session in get_db(): await set_setting(session, "sub_link_pattern", "")
    await callback.answer("✅ حذف شد")
    await callback.message.answer("🗑 حذف شد. تشخیص خودکار فعال.")

@router.callback_query(F.data.startswith("setup_edit:"))
async def start_edit(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    key = callback.data.split(":")[1]
    info = None
    for section in SETTINGS_SCHEMA.values():
        if key in section["items"]:
            info = section["items"][key]
            break
    if not info: return
    async for session in get_db(): current = await get_setting(session, key, info.get("default", ""))
    await state.update_data(setup_key=key, setup_info=info)
    text = f"✏️ **{info['label']}**\n📌 فعلی: `{current or 'خالی'}`\n💡 نمونه: `{info['example']}`\nمقدار جدید:"
    await callback.message.answer(text, parse_mode="Markdown")
    
    state_map = {
        "panel_url": SetupState.waiting_for_panel_url, "panel_api_key": SetupState.waiting_for_panel_api_key,
        "card_number": SetupState.waiting_for_card_number, "card_name": SetupState.waiting_for_card_name,
        "channel_ids": SetupState.waiting_for_channel_ids, "support_username": SetupState.waiting_for_support_username,
        "referral_reward": SetupState.waiting_for_referral_reward, "test_volume_mb": SetupState.waiting_for_test_volume,
        "test_duration_hours": SetupState.waiting_for_test_duration, "test_cooldown_hours": SetupState.waiting_for_test_cooldown,
        "free_config_threshold": SetupState.waiting_for_free_threshold, "help_android": SetupState.waiting_for_help_android,
        "help_ios": SetupState.waiting_for_help_ios, "help_windows": SetupState.waiting_for_help_windows,
        "sub_link_pattern": SetupState.waiting_for_sub_link_pattern, "max_test_per_user": SetupState.waiting_for_max_test,
        "bot_username": SetupState.waiting_for_bot_username, "free_config_volume_gb": SetupState.waiting_for_free_volume,
        "free_config_duration_days": SetupState.waiting_for_free_duration,
    }
    target_state = state_map.get(key)
    if target_state: await state.set_state(target_state)

async def save_setting_handler(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ لغو شد.")
        return
    data = await state.get_data()
    key = data.get("setup_key")
    info = data.get("setup_info", {})
    value = message.text.strip()
    if key == "panel_url":
        if not value.startswith("http"): return await message.answer("❌ با http:// یا https:// شروع شود.")
        value = value.rstrip('/')
    elif key == "channel_ids":
        try:
            ids = [int(cid.strip()) for cid in value.split(",") if cid.strip()]
            if not ids: return await message.answer("❌ حداقل یک آیدی.")
            value = ",".join(str(x) for x in ids)
        except ValueError: return await message.answer("❌ فقط اعداد با کاما.")
    elif key in ["referral_reward", "test_volume_mb", "test_duration_hours", "test_cooldown_hours", "free_config_threshold", "max_test_per_user", "free_config_volume_gb", "free_config_duration_days"]:
        if not value.isdigit(): return await message.answer("❌ فقط عدد.")
    elif key == "support_username": value = value.lstrip("@").strip()
    elif key == "bot_username":
        value = value.lstrip("@").strip()
        if not value: return await message.answer("❌ نام کاربری نمی‌تواند خالی باشد.")
    elif key == "sub_link_pattern":
        if value and "{subId}" not in value and "{sub_id}" not in value: return await message.answer("❌ شامل `{subId}` باشد.", parse_mode="Markdown")
        if value and not value.startswith("http"): return await message.answer("❌ با http:// یا https://.")
        
    async for session in get_db(): await set_setting(session, key, value)
    await state.clear()
    val_display = value[:50] + ("..." if len(value) > 50 else "")
    await message.answer(f"✅ **{info.get('label', key)}**\n`{val_display}`", parse_mode="Markdown")

for state_cls in [
    SetupState.waiting_for_panel_url, SetupState.waiting_for_panel_api_key,
    SetupState.waiting_for_card_number, SetupState.waiting_for_card_name,
    SetupState.waiting_for_channel_ids, SetupState.waiting_for_support_username,
    SetupState.waiting_for_referral_reward, SetupState.waiting_for_test_volume,
    SetupState.waiting_for_test_duration, SetupState.waiting_for_test_cooldown,
    SetupState.waiting_for_free_threshold, SetupState.waiting_for_help_android,
    SetupState.waiting_for_help_ios, SetupState.waiting_for_help_windows,
    SetupState.waiting_for_sub_link_pattern, SetupState.waiting_for_max_test,
    SetupState.waiting_for_bot_username, SetupState.waiting_for_free_volume,
    SetupState.waiting_for_free_duration,
]:
    router.message(state_cls)(save_setting_handler)

@router.callback_query(F.data == "setup_servers")
async def setup_servers(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    async for session in get_db():
        result = await session.execute(select(Server).order_by(Server.priority))
        servers = result.scalars().all()
    if not servers: text = "🌍 **سرورها:**\n⚠️ سروری تنظیم نشده."
    else:
        text = "🌍 **سرورها:**\n"
        for s in servers:
            status = "✅" if s.is_active else "⛔"
            text += f"{status} **{s.name}**\n└ `{s.url}`\n"
    kb_buttons = [
        [InlineKeyboardButton(text="➕ افزودن", callback_data="add_server_start")],
        [InlineKeyboardButton(text="🎯 اینباندها", callback_data="manage_inbounds")],
    ]
    for s in servers:
        kb_buttons.append([
            InlineKeyboardButton(text=f"🧪 {s.name}", callback_data=f"test_server:{s.id}"),
            InlineKeyboardButton(text=f"🗑", callback_data=f"del_server:{s.id}"),
        ])
    kb_buttons.append([InlineKeyboardButton(text="🔙", callback_data="setup_wizard")])
    await safe_edit_or_send(callback, text, InlineKeyboardMarkup(inline_keyboard=kb_buttons), "Markdown")

@router.callback_query(F.data == "add_server_start")
async def add_server_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("📝 **نام سرور:**")
    await state.set_state(SetupState.waiting_for_panel_name)

@router.message(SetupState.waiting_for_panel_name)
async def get_server_name(message: Message, state: FSMContext):
    await state.update_data(server_name=message.text.strip())
    await message.answer("🌐 **آدرس پنل:**")
    await state.set_state(SetupState.waiting_for_panel_url)

@router.message(SetupState.waiting_for_panel_url)
async def get_server_url(message: Message, state: FSMContext):
    url = message.text.strip().rstrip('/')
    if not url.startswith("http"): return await message.answer("❌ با http:// یا https://.")
    await state.update_data(server_url=url)
    await message.answer("🔑 **API Token:**")
    await state.set_state(SetupState.waiting_for_panel_api_key)

@router.message(SetupState.waiting_for_panel_api_key)
async def get_server_api_key(message: Message, state: FSMContext):
    data = await state.get_data()
    api_key = message.text.strip()
    test_msg = await message.answer("🔄 در حال تست...")
    import aiohttp
    try:
        async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"}) as test_session:
            async with test_session.get(f"{data['server_url']}/panel/api/inbounds/options", timeout=15) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    inbounds = result.get("obj", result) if isinstance(result, dict) else result
                    inbound_count = len(inbounds) if isinstance(inbounds, list) else 0
                elif resp.status == 401:
                    await test_msg.edit_text("❌ **Token نامعتبر.**")
                    return
                else:
                    await test_msg.edit_text(f"❌ HTTP {resp.status}.")
                    return
    except Exception as e:
        await test_msg.edit_text(f"❌ خطا: {e}")
        return
        
    async for session in get_db():
        server = Server(name=data["server_name"], url=data["server_url"], api_key=api_key, inbound_id=1, priority=1, is_active=True)
        session.add(server)
        await session.commit()
        await set_setting(session, "panel_url", data["server_url"])
        await set_setting(session, "panel_api_key", api_key)
    await state.clear()
    await test_msg.edit_text(f"✅ **{data['server_name']}** اضافه شد!\n📊 {inbound_count} اینباند", parse_mode="Markdown")

@router.callback_query(F.data.startswith("test_server:"))
async def test_server(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    server_id = int(callback.data.split(":")[1])
    await callback.answer("⏳ در حال تست...")
    res = await panel_api.get_inbound_options(server_id)
    if res["success"]:
        server = res["server"]
        count = len(res["inbounds"])
        samples = [ib.get('remark', '?') for ib in res['inbounds'][:3]]
        await callback.message.answer(f"✅ **{server.name}** | {count} اینباند\n📋 {samples}", parse_mode="Markdown")
    else: await callback.message.answer(f"❌ {res['msg']}", parse_mode="Markdown")

@router.callback_query(F.data.startswith("del_server:"))
async def del_server(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    server_id = int(callback.data.split(":")[1])
    async for session in get_db():
        server = (await session.execute(select(Server).where(Server.id == server_id))).scalar_one_or_none()
        if server:
            name = server.name
            await session.delete(server)
            await session.commit()
    await callback.answer(f"🗑 {name} حذف شد", show_alert=True)
    await setup_servers(callback)

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery):
    from bot.handlers.admin import cmd_admin
    await cmd_admin(callback.message)
