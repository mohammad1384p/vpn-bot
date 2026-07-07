import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, desc, func
from bot.database import Ticket, TicketMessage, Admin, get_db
from bot.config import Config
from bot.auth import is_admin

router = Router()

class TicketState(StatesGroup):
    waiting_for_subject = State()
    waiting_for_message = State()
    admin_replying = State()

TICKET_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎫 تیکت جدید")],
        [KeyboardButton(text="📋 تیکت‌های من")],
        [KeyboardButton(text="🔙 بازگشت به منو")]
    ],
    resize_keyboard=True
)

async def get_all_admin_ids():
    admin_ids = [Config.ADMIN_ID]
    try:
        async for session in get_db():
            result = await session.execute(select(Admin))
            admin_ids.extend([a.telegram_id for a in result.scalars().all()])
    except: pass
    return admin_ids

@router.message(F.text == "🎫 پشتیبانی")
async def support_menu(message: Message):
    await message.answer("🎫 **پشتیبانی:**", reply_markup=TICKET_MENU, parse_mode="Markdown")

@router.message(F.text == "🎫 تیکت‌ها")
async def admin_tickets_menu(message: Message):
    if not await is_admin(message.from_user.id): return
    async for session in get_db():
        open_tickets = (await session.execute(select(Ticket).where(Ticket.status == "open"))).scalars().all()
        all_tickets = (await session.execute(select(Ticket).order_by(desc(Ticket.created_at)).limit(10))).scalars().all()
    
    text = f"🎫 **مدیریت تیکت‌ها:**\n🟢 باز: `{len(open_tickets)}`\n📋 اخیر: `{len(all_tickets)}`\n"
    if all_tickets:
        for t in all_tickets:
            icon = {"open": "🟢", "closed": "🔴", "admin_replied": "🟡"}.get(t.status, "⚪")
            text += f"{icon} #{t.id} | {t.subject[:25]}...\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 تیکت‌های باز", callback_data="admin_tickets_open")],
        [InlineKeyboardButton(text="همه تیکت‌ها", callback_data="admin_tickets_all")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.in_(["admin_tickets_open", "admin_tickets_all"]))
async def admin_list_tickets(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    view_all = callback.data == "admin_tickets_all"
    async for session in get_db():
        if view_all:
            tickets = (await session.execute(select(Ticket).order_by(desc(Ticket.created_at)).limit(20))).scalars().all()
        else:
            tickets = (await session.execute(select(Ticket).where(Ticket.status == "open").order_by(desc(Ticket.created_at)).limit(20))).scalars().all()
    
    if not tickets: return await callback.answer("تیکتی وجود ندارد", show_alert=True)
    
    kb_buttons = []
    for t in tickets:
        icon = {"open": "🟢", "closed": "🔴", "admin_replied": "🟡"}.get(t.status, "⚪")
        kb_buttons.append([InlineKeyboardButton(text=f"{icon} #{t.id} {t.subject[:30]}", callback_data=f"admin_ticket_detail:{t.id}")])
    kb_buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back_to_tickets_menu")])
    await callback.message.edit_text(f"📋 **{'همه تیکت‌ها' if view_all else 'تیکت‌های باز'}:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_ticket_detail:"))
async def admin_ticket_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    ticket_id = int(callback.data.split(":")[1])
    async for session in get_db():
        ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
        msgs = (await session.execute(select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at))).scalars().all()
    if not ticket: return await callback.answer("❌ یافت نشد", show_alert=True)
    
    text = f"🎫 **تیکت #{ticket.id}**\n👤 `{ticket.telegram_id}`\n📝 {ticket.subject}\n🔄 {ticket.status}\n━━━━━━━━━━━━━━\n"
    for m in msgs:
        sender = "👤 کاربر" if m.sender_type == "user" else "🛠 پشتیبانی"
        content = "[عکس]" if m.photo_file_id else (m.text or "")
        text += f"{sender}: {content[:100]}\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 پاسخ", callback_data=f"reply_ticket:{ticket.id}")],
        [InlineKeyboardButton(text="🔴 بستن", callback_data=f"close_ticket:{ticket.id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_tickets_open")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("close_ticket:"))
async def admin_close_ticket(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    ticket_id = int(callback.data.split(":")[1])
    async for session in get_db():
        ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
        if ticket:
            ticket.status = "closed"
            await session.commit()
    await callback.answer("✅ بسته شد", show_alert=True)
    await admin_list_tickets(callback)

@router.callback_query(F.data == "admin_back_to_tickets_menu")
async def admin_back_tickets(callback: CallbackQuery):
    await admin_tickets_menu(callback.message)

@router.message(F.text == "🎫 تیکت جدید")
async def new_ticket(message: Message, state: FSMContext):
    await message.answer("📝 موضوع تیکت را وارد کنید:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ انصراف")]], resize_keyboard=True))
    await state.set_state(TicketState.waiting_for_subject)

@router.message(TicketState.waiting_for_subject, F.text)
async def get_subject(message: Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        from bot.handlers.start import MAIN_MENU
        return await message.answer("لغو شد.", reply_markup=MAIN_MENU)
    subject = message.text.strip()[:200]
    async for session in get_db():
        ticket = Ticket(telegram_id=message.from_user.id, subject=subject, status="open")
        session.add(ticket)
        await session.commit()
        ticket_id = ticket.id
    await state.update_data(ticket_id=ticket_id, subject=subject)
    await message.answer(f"✅ تیکت #{ticket_id} ایجاد شد.\nپیام خود را ارسال کنید:")
    await state.set_state(TicketState.waiting_for_message)

@router.message(TicketState.waiting_for_message, F.text | F.photo)
async def send_ticket_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ticket_id = data["ticket_id"]
    async for session in get_db():
        msg = TicketMessage(
            ticket_id=ticket_id, sender_id=message.from_user.id, sender_type="user",
            text=message.text if message.text else (message.caption or "[عکس]"),
            photo_file_id=message.photo[-1].file_id if message.photo else None
        )
        session.add(msg)
        await session.commit()
    await state.clear()
    from bot.handlers.start import MAIN_MENU
    await message.answer("✅ پیام ارسال شد.", reply_markup=TICKET_MENU)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 پاسخ", callback_data=f"reply_ticket:{ticket_id}")]])
    content = message.text or message.caption or '[عکس]'
    text = f"🎫 **تیکت #{ticket_id}**\n👤 `{message.from_user.id}`\n📝 {data.get('subject', 'نامشخص')}\n💬 {content}"
    admin_ids = await get_all_admin_ids()
    for admin_id in admin_ids:
        try:
            if message.photo: await bot.send_photo(admin_id, message.photo[-1].file_id, caption=text, reply_markup=kb, parse_mode="Markdown")
            else: await bot.send_message(admin_id, text, reply_markup=kb, parse_mode="Markdown")
        except: pass

@router.message(F.text == "📋 تیکت‌های من")
async def my_tickets(message: Message):
    async for session in get_db():
        result = await session.execute(select(Ticket).where(Ticket.telegram_id == message.from_user.id).order_by(desc(Ticket.created_at)).limit(10))
        tickets = result.scalars().all()
    if not tickets: return await message.answer("📭 هیچ تیکتی ندارید.", reply_markup=TICKET_MENU)
    text = "📋 **تیکت‌های شما:**\n"
    kb_buttons = []
    for t in tickets:
        status_icon = {"open": "🟢", "closed": "🔴", "admin_replied": "🟡"}.get(t.status, "⚪")
        text += f"{status_icon} #{t.id} | {t.subject[:30]}\n"
        kb_buttons.append([InlineKeyboardButton(text=f"#{t.id} {t.subject[:40]}", callback_data=f"view_ticket:{t.id}")])
    kb_buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_ticket_menu")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("view_ticket:"))
async def view_ticket(callback: CallbackQuery):
    ticket_id = int(callback.data.split(":")[1])
    async for session in get_db():
        ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
    if not ticket or ticket.telegram_id != callback.from_user.id: return await callback.answer("دسترسی ندارید.", show_alert=True)
    async for session in get_db():
        msgs_result = await session.execute(select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at))
        messages = msgs_result.scalars().all()
    text = f"🎫 **تیکت #{ticket.id}**\n📝 {ticket.subject}\n"
    for m in messages:
        sender = "👤 شما" if m.sender_type == "user" else "🛠 پشتیبانی"
        text += f"{sender}:\n{m.text}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 پیام جدید", callback_data=f"reply_ticket:{ticket_id}")]])
    await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "back_ticket_menu")
async def back_ticket_menu(callback: CallbackQuery):
    await callback.message.answer("🎫 **پشتیبانی:**", reply_markup=TICKET_MENU, parse_mode="Markdown")

@router.callback_query(F.data.startswith("reply_ticket:"))
async def admin_start_reply(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return await callback.answer("فقط ادمین", show_alert=True)
    ticket_id = int(callback.data.split(":")[1])
    await state.update_data(ticket_id=ticket_id)
    async for session in get_db():
        ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
        msgs_result = await session.execute(select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at))
        messages = msgs_result.scalars().all()
    text = f"🎫 **پاسخ #{ticket_id}**\n👤 `{ticket.telegram_id}`\n📝 {ticket.subject}\n"
    for m in messages:
        sender = "👤 کاربر" if m.sender_type == "user" else "🛠 شما"
        text += f"{sender}:\n{m.text}\n"
    text += "\n✍️ پاسخ:"
    await callback.message.answer(text, parse_mode="Markdown")
    await state.set_state(TicketState.admin_replying)

@router.message(TicketState.admin_replying, F.text | F.photo)
async def admin_send_reply(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ticket_id = data["ticket_id"]
    async for session in get_db():
        ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
    if not ticket:
        await state.clear()
        return
    async for session in get_db():
        msg = TicketMessage(
            ticket_id=ticket_id, sender_id=message.from_user.id, sender_type="admin",
            text=message.text if message.text else (message.caption or "[عکس]"),
            photo_file_id=message.photo[-1].file_id if message.photo else None
        )
        session.add(msg)
        ticket.status = "admin_replied"
        await session.commit()
    user_id = ticket.telegram_id
    await state.clear()
    await message.answer(f"✅ پاسخ به #{ticket_id} ارسال شد.")
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 مشاهده", callback_data=f"view_ticket:{ticket_id}")]])
        content = message.text or message.caption or '[عکس]'
        reply_text = f"🛠 **پاسخ #{ticket_id}:**\n{content}"
        if message.photo: await bot.send_photo(user_id, message.photo[-1].file_id, caption=reply_text, reply_markup=kb, parse_mode="Markdown")
        else: await bot.send_message(user_id, reply_text, reply_markup=kb, parse_mode="Markdown")
    except: pass
