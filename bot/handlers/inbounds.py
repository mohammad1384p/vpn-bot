from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from bot.database import get_db, get_setting, set_setting
from bot.panel_api import panel_api
from bot.auth import is_admin

router = Router()

@router.callback_query(F.data == "manage_inbounds")
async def manage_inbounds(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("❌ دسترسی ندارید", show_alert=True)
    async for session in get_db():
        saved = await get_setting(session, "selected_inbound_ids", "")
        saved_ids = [int(x) for x in saved.split(",") if x] if saved else []
    res = await panel_api.get_inbound_options()
    if not res["success"]: return await callback.message.answer(f"❌ خطا: {res['msg']}")
    inbounds = res["inbounds"]
    if not inbounds: return await callback.message.answer("⚠️ هیچ اینباندی یافت نشد.")
    text = f"🎯 **انتخاب اینباندها:**\n✅ فعلی: {len(saved_ids)}"
    kb_buttons = []
    for ib in inbounds:
        ib_id = ib.get('id')
        ib_remark = ib.get('remark') or f"Inbound {ib_id}"
        ib_protocol = ib.get('protocol', '?')
        ib_port = ib.get('port', '?')
        status = '✅' if ib_id in saved_ids else '⬜'
        kb_buttons.append([InlineKeyboardButton(
            text=f"{status} {ib_remark} ({ib_protocol}:{ib_port})",
            callback_data=f"toggle_inbound:{ib_id}"
        )])
    kb_buttons.append([InlineKeyboardButton(text="✅ انتخاب همه", callback_data="select_all_inbounds")])
    kb_buttons.append([InlineKeyboardButton(text="❌ حذف همه", callback_data="clear_all_inbounds")])
    kb_buttons.append([InlineKeyboardButton(text="💾 بازگشت", callback_data="setup_servers")])
    try: await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")
    except TelegramBadRequest: await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("toggle_inbound:"))
async def toggle_inbound(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    inbound_id = int(callback.data.split(":")[1])
    async for session in get_db():
        saved = await get_setting(session, "selected_inbound_ids", "")
        saved_ids = [int(x) for x in saved.split(",") if x] if saved else []
        if inbound_id in saved_ids: saved_ids.remove(inbound_id)
        else: saved_ids.append(inbound_id)
        await set_setting(session, "selected_inbound_ids", ",".join(str(x) for x in saved_ids))
    await manage_inbounds(callback)

@router.callback_query(F.data == "select_all_inbounds")
async def select_all_inbounds(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    res = await panel_api.get_inbound_options()
    if not res["success"]: return await callback.answer(f"خطا: {res['msg']}", show_alert=True)
    all_ids = [ib["id"] for ib in res["inbounds"]]
    async for session in get_db():
        await set_setting(session, "selected_inbound_ids", ",".join(str(x) for x in all_ids))
    await manage_inbounds(callback)

@router.callback_query(F.data == "clear_all_inbounds")
async def clear_all_inbounds(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    async for session in get_db():
        await set_setting(session, "selected_inbound_ids", "")
    await manage_inbounds(callback)

async def get_selected_inbound_ids():
    async for session in get_db():
        saved = await get_setting(session, "selected_inbound_ids", "")
        if saved: return [int(x) for x in saved.split(",") if x]
    return []
