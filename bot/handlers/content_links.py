from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func, delete
from bot.database import get_db, ContentLink, User
from bot.auth import is_admin
from bot.handlers.start import check_user_membership, PHONE_KB, show_main_menu, requires_phone_auth
import uuid

router = Router()

class ContentLinkState(StatesGroup):
    waiting_for_title = State()
    waiting_for_content_type = State()
    waiting_for_content = State()
    waiting_for_ad_choice = State()
    waiting_for_ad_text = State()
    waiting_for_ad_photo = State()

@router.message(Command("start"), F.text.regexp(r"^/start\s+content_"))
async def handle_content_link_start(message: Message, bot: Bot):
    parts = message.text.split()
    param = parts[1]
    code = param[8:]
    not_joined_channels = await check_user_membership(bot, message.from_user.id)
    if not_joined_channels:
        kb_buttons = [[InlineKeyboardButton(text=f"📢 عضویت در {ch['title']}", url=f"https://t.me/{ch['username']}")] for ch in not_joined_channels]
        kb_buttons.append([InlineKeyboardButton(text="✅ بررسی عضویت", callback_data=f"check_join_content:{code}")])
        await message.answer("👋 برای مشاهده این محتوا، ابتدا در کانال‌های زیر عضو شوید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))
        return
    async for session in get_db():
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one_or_none()
    if not user:
        await message.answer("⚠️ لطفاً ابتدا /start را بزنید.")
        return
    if requires_phone_auth(user):
        await message.answer("🔐 چون با لینک زیرمجموعه وارد شده‌اید، برای مشاهده این محتوا ابتدا شماره تماس خود را تایید کنید.", reply_markup=PHONE_KB)
        return
    async for session in get_db():
        result = await session.execute(select(ContentLink).where(ContentLink.code == code))
        content_link = result.scalar_one_or_none()
        if not content_link:
            await message.answer("❌ **لینک نامعتبر!**\nاین محتوا یافت نشد.", parse_mode="Markdown")
            return
        if not content_link.is_active:
            await message.answer("⛔ **غیرفعال!**", parse_mode="Markdown")
            return
        content_link.views += 1
        await session.commit()
        await session.refresh(content_link)
    await send_content_to_user(message, content_link, bot)

@router.callback_query(F.data.startswith("check_join_content:"))
async def check_join_content_callback(callback: CallbackQuery, bot: Bot):
    code = callback.data.split(":")[1]
    await callback.answer("⏳ در حال بررسی...")
    not_joined_channels = await check_user_membership(bot, callback.from_user.id)
    if not not_joined_channels:
        await callback.message.delete()
        class FakeMsg:
            def __init__(self, cb, c):
                self.from_user = cb.from_user
                self.chat = cb.message.chat
                self.text = f"/start content_{c}"
            async def answer(self, *a, **k): return await callback.message.answer(*a, **k)
        await handle_content_link_start(FakeMsg(callback, code), bot)
    else:
        kb_buttons = [[InlineKeyboardButton(text=f"📢 عضویت در {ch['title']}", url=f"https://t.me/{ch['username']}")] for ch in not_joined_channels]
        kb_buttons.append([InlineKeyboardButton(text="✅ بررسی مجدد", callback_data=f"check_join_content:{code}")])
        await callback.message.edit_text("⚠️ هنوز در تمام کانال‌ها عضو نشده‌اید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))

async def send_content_to_user(message: Message, content_link: ContentLink, bot: Bot):
    if content_link.has_ad:
        if content_link.ad_photo_id: await bot.send_photo(message.chat.id, content_link.ad_photo_id, caption=content_link.ad_text or "📢 تبلیغ", parse_mode="Markdown")
        elif content_link.ad_text: await bot.send_message(message.chat.id, f"📢 **تبلیغ:**\n{content_link.ad_text}", parse_mode="Markdown")
    try:
        if content_link.content_type == "text": await bot.send_message(message.chat.id, content_link.content_text or "", parse_mode="Markdown")
        elif content_link.content_type == "photo": await bot.send_photo(message.chat.id, content_link.content_file_id, caption=content_link.content_caption or "", parse_mode="Markdown")
        elif content_link.content_type == "document": await bot.send_document(message.chat.id, content_link.content_file_id, caption=content_link.content_caption or "", parse_mode="Markdown")
        elif content_link.content_type == "video": await bot.send_video(message.chat.id, content_link.content_file_id, caption=content_link.content_caption or "", parse_mode="Markdown")
        elif content_link.content_type == "audio": await bot.send_audio(message.chat.id, content_link.content_file_id, caption=content_link.content_caption or "", parse_mode="Markdown")
        elif content_link.content_type == "voice": await bot.send_voice(message.chat.id, content_link.content_file_id, caption=content_link.content_caption or "", parse_mode="Markdown")
    except Exception as e:
        await bot.send_message(message.chat.id, f"❌ خطا: {e}")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 شروع ربات", callback_data="start_bot_from_content")]])
    await bot.send_message(message.chat.id, "🎉 **محتوا دریافت شد!**", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "start_bot_from_content")
async def start_bot_from_content(callback: CallbackQuery, bot: Bot):
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
    if not user:
        await callback.message.answer("⚠️ لطفاً ابتدا /start را بزنید.")
        return
    if requires_phone_auth(user):
        await callback.message.answer("🔐 چون با لینک زیرمجموعه وارد شده‌اید، لطفاً شماره تماس خود را تایید کنید.", reply_markup=PHONE_KB)
        return
    await callback.message.delete()
    class FakeMsg:
        def __init__(self, cb):
            self.from_user = cb.from_user
            self.chat = cb.message.chat
        async def answer(self, *a, **k): return await callback.message.answer(*a, **k)
    await show_main_menu(FakeMsg(callback))

@router.message(F.text == "📢 لینک‌های محتوا")
async def content_links_menu(message: Message):
    if not await is_admin(message.from_user.id): return
    async for session in get_db():
        result = await session.execute(select(ContentLink).order_by(ContentLink.created_at.desc()))
        links = result.scalars().all()
        total_views = (await session.execute(select(func.sum(ContentLink.views)))).scalar() or 0
    text = f"📢 **لینک‌های محتوا:**\n📊 کل بازدیدها: `{total_views}`\n"
    if not links: text += "_هنوز لینکی ساخته نشده._\n"
    else:
        for link in links[:10]:
            status = "✅" if link.is_active else "⛔"
            type_emoji = {"text": "📝", "photo": "🖼", "document": "📄", "video": "🎬", "audio": "🎵", "voice": "🎤"}.get(link.content_type, "📎")
            title = link.title or link.code
            text += f"{status} {type_emoji} **{title}**\n└ `{link.views}` بازدید | کد: `{link.code[:8]}...`\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن لینک جدید", callback_data="add_content_link")],
        [InlineKeyboardButton(text="📋 لیست کامل", callback_data="list_content_links")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "list_content_links")
async def list_all_content_links(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    async for session in get_db():
        result = await session.execute(select(ContentLink).order_by(ContentLink.created_at.desc()))
        links = result.scalars().all()
    if not links: return await callback.answer("لینکی وجود ندارد", show_alert=True)
    kb_buttons = []
    for link in links:
        status = "✅" if link.is_active else "⛔"
        type_emoji = {"text": "📝", "photo": "🖼", "document": "📄", "video": "🎬", "audio": "🎵", "voice": "🎤"}.get(link.content_type, "📎")
        title = (link.title or link.code)[:25]
        kb_buttons.append([InlineKeyboardButton(text=f"{status} {type_emoji} {title} ({link.views}👁)", callback_data=f"edit_content_link:{link.id}")])
    kb_buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_content_menu")])
    await callback.message.edit_text("📋 **لیست لینک‌ها:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.callback_query(F.data == "add_content_link")
async def add_content_link_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("📝 **ساخت لینک محتوای جدید:**\nعنوان لینک را وارد کنید:")
    await state.set_state(ContentLinkState.waiting_for_title)

@router.message(ContentLinkState.waiting_for_title, F.text)
async def add_content_link_title(message: Message, state: FSMContext):
    title = message.text.strip()[:200]
    await state.update_data(title=title)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 متن", callback_data="content_type:text")],
        [InlineKeyboardButton(text="🖼 عکس", callback_data="content_type:photo")],
        [InlineKeyboardButton(text="📄 فایل", callback_data="content_type:document")],
        [InlineKeyboardButton(text="🎬 ویدیو", callback_data="content_type:video")],
        [InlineKeyboardButton(text="🎵 صدا", callback_data="content_type:audio")],
        [InlineKeyboardButton(text="🎤 ویس", callback_data="content_type:voice")],
    ])
    await message.answer(f"✅ عنوان: **{title}**\nنوع محتوا:", reply_markup=kb, parse_mode="Markdown")
    await state.set_state(ContentLinkState.waiting_for_content_type)

@router.callback_query(F.data.startswith("content_type:"))
async def add_content_link_type(callback: CallbackQuery, state: FSMContext):
    content_type = callback.data.split(":")[1]
    await state.update_data(content_type=content_type)
    type_names = {"text": "📝 **متن محتوا** را ارسال کنید:", "photo": "🖼 **عکس** را ارسال کنید:", "document": "📄 **فایل** را ارسال کنید:", "video": "🎬 **ویدیو** را ارسال کنید:", "audio": "🎵 **فایل صوتی** را ارسال کنید:", "voice": "🎤 **ویس** را ارسال کنید:"}
    await callback.message.answer(type_names.get(content_type, "محتوا را ارسال کنید:"))
    await state.set_state(ContentLinkState.waiting_for_content)

@router.message(ContentLinkState.waiting_for_content)
async def add_content_link_content(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    content_type = data.get("content_type")
    content_text, content_file_id, content_caption = None, None, None
    if content_type == "text":
        if not message.text: return await message.answer("❌ لطفاً متن ارسال کنید.")
        content_text = message.text
    elif content_type == "photo":
        if not message.photo: return await message.answer("❌ لطفاً عکس ارسال کنید.")
        content_file_id = message.photo[-1].file_id
        content_caption = message.caption
    elif content_type == "document":
        if not message.document: return await message.answer("❌ لطفاً فایل ارسال کنید.")
        content_file_id = message.document.file_id
        content_caption = message.caption
    elif content_type == "video":
        if not message.video: return await message.answer("❌ لطفاً ویدیو ارسال کنید.")
        content_file_id = message.video.file_id
        content_caption = message.caption
    elif content_type == "audio":
        if not message.audio: return await message.answer("❌ لطفاً فایل صوتی ارسال کنید.")
        content_file_id = message.audio.file_id
        content_caption = message.caption
    elif content_type == "voice":
        if not message.voice: return await message.answer("❌ لطفاً ویس ارسال کنید.")
        content_file_id = message.voice.file_id
        content_caption = message.caption
    await state.update_data(content_text=content_text, content_file_id=content_file_id, content_caption=content_caption)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، تبلیغ اضافه کنم", callback_data="has_ad:yes")],
        [InlineKeyboardButton(text="❌ خیر، بدون تبلیغ", callback_data="has_ad:no")],
    ])
    await message.answer("✅ محتوا دریافت شد!\nآیا می‌خواهید **تبلیغ** همراه این محتوا ارسال شود?", reply_markup=kb, parse_mode="Markdown")
    await state.set_state(ContentLinkState.waiting_for_ad_choice)

@router.callback_query(F.data.startswith("has_ad:"))
async def add_content_link_ad_choice(callback: CallbackQuery, state: FSMContext):
    has_ad = callback.data.split(":")[1] == "yes"
    if not has_ad: await save_content_link(callback, state, has_ad=False)
    else:
        await callback.message.answer("📢 **متن تبلیغ** را وارد کنید:")
        await state.update_data(has_ad=True)
        await state.set_state(ContentLinkState.waiting_for_ad_text)

@router.message(ContentLinkState.waiting_for_ad_text, F.text)
async def add_content_link_ad_text(message: Message, state: FSMContext):
    await state.update_data(ad_text=message.text[:2000])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، عکس تبلیغ هم دارم", callback_data="ad_has_photo:yes")],
        [InlineKeyboardButton(text="❌ خیر، فقط متن", callback_data="ad_has_photo:no")],
    ])
    await message.answer("✅ متن تبلیغ ذخیره شد!\nآیا **عکس تبلیغ** هم دارید?", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("ad_has_photo:"))
async def add_content_link_ad_photo_choice(callback: CallbackQuery, state: FSMContext):
    has_photo = callback.data.split(":")[1] == "yes"
    if not has_photo: await save_content_link(callback, state, has_ad=True, ad_has_photo=False)
    else:
        await callback.message.answer("🖼 **عکس تبلیغ** را ارسال کنید:")
        await state.set_state(ContentLinkState.waiting_for_ad_photo)

@router.message(ContentLinkState.waiting_for_ad_photo, F.photo)
async def add_content_link_ad_photo(message: Message, state: FSMContext):
    await state.update_data(ad_photo_id=message.photo[-1].file_id)
    await save_content_link(message, state, has_ad=True, ad_has_photo=True)

async def save_content_link(event, state: FSMContext, has_ad: bool, ad_has_photo: bool = False):
    data = await state.get_data()
    code = uuid.uuid4().hex[:12]
    async for session in get_db():
        admin_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
        content_link = ContentLink(
            code=code, title=data.get("title"), content_type=data.get("content_type"),
            content_text=data.get("content_text"), content_file_id=data.get("content_file_id"),
            content_caption=data.get("content_caption"), has_ad=has_ad,
            ad_text=data.get("ad_text") if has_ad else None,
            ad_photo_id=data.get("ad_photo_id") if (has_ad and ad_has_photo) else None,
            created_by=admin_id, views=0, is_active=True
        )
        session.add(content_link)
        await session.commit()
    await state.clear()
    bot = event.bot if hasattr(event, 'bot') else event.message.bot
    bot_username = (await bot.get_me()).username
    share_link = f"https://t.me/{bot_username}?start=content_{code}"
    type_names = {"text": "📝 متن", "photo": "🖼 عکس", "document": "📄 فایل", "video": "🎬 ویدیو", "audio": "🎵 صدا", "voice": "🎤 ویس"}
    msg = event.message if hasattr(event, 'message') else event
    await msg.answer(
        f"✅ **لینک محتوا ساخته شد!**\n📝 عنوان: **{data.get('title')}**\n📎 نوع: {type_names.get(data.get('content_type'), '?')}\n📢 تبلیغ: {'✅ بله' if has_ad else '❌ خیر'}\n🔗 **لینک اشتراک:**\n`{share_link}`",
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("edit_content_link:"))
async def edit_content_link_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    link_id = int(callback.data.split(":")[1])
    async for session in get_db():
        result = await session.execute(select(ContentLink).where(ContentLink.id == link_id))
        content_link = result.scalar_one_or_none()
    if not content_link: return await callback.answer("❌ یافت نشد", show_alert=True)
    bot_username = (await callback.bot.get_me()).username
    share_link = f"https://t.me/{bot_username}?start=content_{content_link.code}"
    status = "✅ فعال" if content_link.is_active else "⛔ غیرفعال"
    type_names = {"text": "📝 متن", "photo": "🖼 عکس", "document": "📄 فایل", "video": "🎬 ویدیو", "audio": "🎵 صدا", "voice": "🎤 ویس"}
    text = (
        f"📝 **ویرایش لینک**\n🏷 عنوان: **{content_link.title or 'بدون عنوان'}**\n📎 نوع: {type_names.get(content_link.content_type, '?')}\n"
        f"📊 بازدید: `{content_link.views}`\n📢 تبلیغ: {'✅ بله' if content_link.has_ad else '❌ خیر'}\n🔄 وضعیت: {status}\n🔗 **لینک:**\n`{share_link}`"
    )
    toggle_text = "⛔ غیرفعال" if content_link.is_active else "✅ فعال"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_content_link:{link_id}")],
        [InlineKeyboardButton(text="📋 کپی لینک", callback_data=f"copy_content_link:{link_id}")],
        [InlineKeyboardButton(text="🗑 حذف", callback_data=f"delete_content_link:{link_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="list_content_links")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("toggle_content_link:"))
async def toggle_content_link(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    link_id = int(callback.data.split(":")[1])
    async for session in get_db():
        result = await session.execute(select(ContentLink).where(ContentLink.id == link_id))
        content_link = result.scalar_one_or_none()
        if content_link:
            content_link.is_active = not content_link.is_active
            await session.commit()
            status = "فعال ✅" if content_link.is_active else "غیرفعال ⛔"
    await callback.answer(f"✅ {status}")
    await edit_content_link_menu(callback)

@router.callback_query(F.data.startswith("copy_content_link:"))
async def copy_content_link(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    link_id = int(callback.data.split(":")[1])
    async for session in get_db():
        result = await session.execute(select(ContentLink).where(ContentLink.id == link_id))
        content_link = result.scalar_one_or_none()
    if content_link:
        bot_username = (await callback.bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start=content_{content_link.code}"
        await callback.message.answer(f"🔗 **لینک {content_link.title or content_link.code}:**\n`{share_link}`", parse_mode="Markdown")
        await callback.answer("✅ لینک ارسال شد")

@router.callback_query(F.data.startswith("delete_content_link:"))
async def delete_content_link(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    link_id = int(callback.data.split(":")[1])
    async for session in get_db():
        await session.execute(delete(ContentLink).where(ContentLink.id == link_id))
        await session.commit()
    await callback.answer("🗑 حذف شد", show_alert=True)
    await list_all_content_links(callback)

@router.callback_query(F.data == "back_to_content_menu")
async def back_to_content_menu(callback: CallbackQuery):
    class FakeMsg:
        def __init__(self, cb): self.from_user = cb.from_user
        async def answer(self, *a, **k): return await callback.message.answer(*a, **k)
    await content_links_menu(FakeMsg(callback))
