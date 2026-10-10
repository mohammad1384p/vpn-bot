// Port of the sub-admin CRUD part of bot/handlers/admin.py.
import { api } from 'sdk';
import { db } from 'sdk';
import { eq } from 'sdk/db';
import { admins } from '../../schema.js';
import { getSuperAdminId, isAdmin } from '../auth.js';
import { setState, getState, clearState } from '../state.js';
import { ADMIN_MENU, CANCEL_MENU } from '../keyboards.js';

async function renderAdminsList(chatId) {
  const superId = await getSuperAdminId();
  const rows = await db.select().from(admins).all();
  let text = `👮 **ادمین‌ها**\n👑 سوپرادمین: \`${superId}\`\n\n`;
  const kb = rows.map((a) => [{ text: `${a.name || a.telegramId} (${a.role})`, callback_data: `admin_detail:${a.telegramId}` }]);
  kb.push([{ text: '➕ افزودن ادمین', callback_data: 'admin_add' }]);
  await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kb }, parse_mode: 'Markdown' });
}

export async function adminsMenu(message) {
  const superId = await getSuperAdminId();
  if (message.from.id !== superId) return; // only the super admin manages sub-admins
  await renderAdminsList(message.chat.id);
}

export async function adminDetailCallback(callback) {
  const superId = await getSuperAdminId();
  if (callback.from.id !== superId) return;
  const targetId = parseInt(callback.data.split(':')[1], 10);
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  const kb = { inline_keyboard: [[{ text: '🗑 حذف ادمین', callback_data: `admin_remove:${targetId}` }]] };
  await api.sendMessage({ chat_id: callback.message.chat.id, text: `👮 ادمین \`${targetId}\``, reply_markup: kb, parse_mode: 'Markdown' });
}

export async function adminRemoveCallback(callback) {
  const superId = await getSuperAdminId();
  if (callback.from.id !== superId) return;
  const targetId = parseInt(callback.data.split(':')[1], 10);
  await db.delete(admins).where(eq(admins.telegramId, targetId)).run();
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '🗑 حذف شد' });
  try { await api.sendMessage({ chat_id: targetId, text: '⚠️ دسترسی ادمین شما لغو شد.' }); } catch { /* ignore */ }
}

export async function adminAddCallback(callback) {
  const superId = await getSuperAdminId();
  if (callback.from.id !== superId) return;
  await setState(callback.from.id, 'admin:admin_add', {});
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await api.sendMessage({
    chat_id: callback.message.chat.id,
    text: '➕ آیدی عددی تلگرام کاربر جدید را ارسال کنید (و در صورت تمایل، نام او را با فاصله بعد از آیدی بنویسید):\nمثال: `123456789 علی`',
    parse_mode: 'Markdown', reply_markup: CANCEL_MENU,
  });
}

export async function processAdminAdd(message) {
  if (message.text === '❌ انصراف') {
    await clearState(message.from.id);
    return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU });
  }
  const parts = (message.text || '').trim().split(/\s+/);
  const targetId = parseInt(parts[0], 10);
  const name = parts.slice(1).join(' ') || null;
  if (Number.isNaN(targetId)) return api.sendMessage({ chat_id: message.chat.id, text: '❌ آیدی نامعتبر است.' });
  await db.insert(admins).values({ telegramId: targetId, name, role: 'admin' })
    .onConflictDoUpdate({ target: admins.telegramId, set: { name, role: 'admin' } }).run();
  await clearState(message.from.id);
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ کاربر \`${targetId}\` به عنوان ادمین اضافه شد.`, parse_mode: 'Markdown', reply_markup: ADMIN_MENU });
  try { await api.sendMessage({ chat_id: targetId, text: '🎉 شما به عنوان ادمین ربات انتخاب شدید!' }); } catch { /* ignore */ }
}
