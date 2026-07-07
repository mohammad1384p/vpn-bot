from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from bot.database import get_db, Server
from bot.panel_api import panel_api
from bot.auth import is_admin
import asyncio

router = Router()

def format_bytes(bytes_val: int) -> str:
    if not bytes_val or bytes_val <= 0: return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}" if bytes_val >= 10 else f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"

def progress_bar(percent: float, length: int = 10) -> str:
    filled = int((percent / 100) * length)
    return "█" * filled + "░" * (length - filled)

@router.message(F.text == "🖥 مانیتورینگ")
async def monitoring_menu(message: Message):
    if not await is_admin(message.from_user.id): return
    async for session in get_db():
        result = await session.execute(select(Server).where(Server.is_active == True).order_by(Server.priority))
        servers = result.scalars().all()
    text = "🖥 **مانیتورینگ سرور:**\nسرور مورد نظر را انتخاب کنید:"
    kb_buttons = []
    for s in servers:
        kb_buttons.append([InlineKeyboardButton(text=f"🖥 {s.name}", callback_data=f"server_status:{s.id}")])
    kb_buttons.append([InlineKeyboardButton(text="👥 گروه‌های کلاینت", callback_data="client_groups")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("server_status:"))
async def server_status(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    server_id = int(callback.data.split(":")[1])
    await callback.answer("⏳ در حال دریافت اطلاعات...")
    status = await panel_api.get_server_status(server_id)
    if not status["success"]: return await callback.message.answer(f"❌ خطا: {status['msg']}")
    
    ram_percent = (status["mem_current"] / status["mem_total"] * 100) if status["mem_total"] > 0 else 0
    swap_percent = (status["swap_current"] / status["swap_total"] * 100) if status["swap_total"] > 0 else 0
    text = (
        f"🖥 **{status['server'].name}**\n"
        f"⚙️ **CPU:** `{status['cpu']:.1f}%` {progress_bar(status['cpu'])}\n"
        f"💾 **RAM:** `{format_bytes(status['mem_current'])}` / `{format_bytes(status['mem_total'])}` ({ram_percent:.1f}%) {progress_bar(ram_percent)}\n"
        f"📀 **Swap:** `{format_bytes(status['swap_current'])}` / `{format_bytes(status['swap_total'])}` ({swap_percent:.1f}%)\n"
    )
    disks = status.get("disk", [])
    if disks:
        if isinstance(disks, dict): disks = [disks]
        elif not isinstance(disks, list): disks = []
        if disks:
            text += "💿 **Disk:**\n"
            for disk in disks[:3]:
                current = disk.get("current", 0)
                total = disk.get("total", 1)
                percent = (current / total * 100) if total > 0 else 0
                text += f"└ `{format_bytes(current)}` / `{format_bytes(total)}` ({percent:.1f}%)\n"
            text += "\n"
    net_io = status.get("net_io", {})
    if net_io:
        text += f"🌐 **Network I/O:**\n└ ⬆️ Up: `{format_bytes(net_io.get('up', 0))}`\n└ ⬇️ Down: `{format_bytes(net_io.get('down', 0))}`\n"
    loads = status.get("loads", [0, 0, 0])
    if not isinstance(loads, list): loads = [0, 0, 0]
    text += f"📈 **Load Average:**\n└ 1m: `{loads[0]:.2f}` | 5m: `{loads[1]:.2f}` | 15m: `{loads[2]:.2f}`\n"
    text += f"🔌 **Connections:**\n└ TCP: `{status['tcp_count']}` | UDP: `{status['udp_count']}`\n"
    xray_state = status.get("xray_state", "unknown")
    state_emoji = "✅" if xray_state == "running" else "⛔"
    text += f"{state_emoji} **Xray:** `{xray_state}`\n"
    uptime = status.get("app_uptime", 0)
    uptime_hours = uptime // 3600
    uptime_mins = (uptime % 3600) // 60
    text += f"⏱ **Uptime:** `{uptime_hours}h {uptime_mins}m`"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 بروزرسانی", callback_data=f"server_status:{server_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_monitoring")],
    ])
    try: await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception: await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "client_groups")
async def client_groups_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    await callback.answer("⏳ در حال دریافت...")
    res = await panel_api.get_client_groups()
    if not res["success"]: return await callback.message.answer(f"❌ خطا: {res['msg']}")
    groups = res["groups"]
    if not groups: text = "👥 **گروه‌های کلاینت:**\n_هنوز گروهی ایجاد نشده._"
    else:
        text = f"👥 **گروه‌های کلاینت:** ({len(groups)} گروه)\n"
        for g in groups:
            name = g.get("name", "بدون نام")
            count = g.get("count", 0)
            text += f"📁 **{name}** - `{count}` عضو\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="client_groups")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_monitoring")],
    ])
    try: await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception: await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "back_to_monitoring")
async def back_to_monitoring(callback: CallbackQuery):
    class FakeMsg:
        def __init__(self, cb): self.from_user = cb.from_user
        async def answer(self, *a, **k): return await callback.message.answer(*a, **k)
    await monitoring_menu(FakeMsg(callback))
