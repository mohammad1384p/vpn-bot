// Port of the user-management part of bot/handlers/admin.py.
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import {
  getUserByTelegramId, getUserByPhone, updateUser, countUsers, listUsersPage,
} from '../db/users.js';
import { listConfigsByUser } from '../db/configs.js';
import { sumApprovedByUser } from '../db/payments.js';
import { setState, getState, clearState } from '../state.js';
import { formatNumber, formatPhoneAdmin } from '../helpers.js';
import { ADMIN_MENU, CANCEL_MENU } from '../keyboards.js';

const PAGE_SIZE = 10;

export async function usersMenu(message) {
  if (!(await isAdmin(message.from.id))) return;
  await listUsersPageView(message.chat.id, 1);
  await api.sendMessage({ chat_id: message.chat.id, text: '🔎 برای جستجوی یک کاربر خاص، آیدی عددی یا شماره تماس او را ارسال کنید.', reply_markup: CANCEL_MENU });
  await setState(message.from.id, 'admin:user_search', {});
}

export async function listUsersPageView(chatId, page) {
  const total = await countUsers();
  const rows = await listUsersPage(page, PAGE_SIZE);
  if (!rows.length) {
    await api.sendMessage({ chat_id: chatId, text: '👥 کاربری یافت نشد.' });
    return;
  }
  let text = `👥 **کاربران (صفحه ${page}/${Math.max(1, Math.ceil(total / PAGE_SIZE))}) — مجموع ${total}**\n\n`;
  const kbRows = [];
  for (const u of rows) {
    text += `\`${u.telegramId}\` ${u.isBlocked ? '⛔' : '✅'} | 💰${formatNumber(u.wallet || 0)} | خرید:${formatNumber(u.totalSpent || 0)}\n`;
    kbRows.push([{ text: `👤 ${u.telegramId}`, callback_data: `user_detail:${u.telegramId}` }]);
  }
  const navRow = [];
  if (page > 1) navRow.push({ text: '⬅️ قبلی', callback_data: `users_page:${page - 1}` });
  if (page * PAGE_SIZE < total) navRow.push({ text: 'بعدی ➡️', callback_data: `users_page:${page + 1}` });
  if (navRow.length) kbRows.push(navRow);
  await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kbRows }, parse_mode: 'Markdown' });
}

export async function usersPageCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const page = parseInt(callback.data.split(':')[1], 10);
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await listUsersPageView(callback.message.chat.id, page);
}

export async function processUserSearch(message) {
  const text = (message.text || '').trim();
  if (text === '❌ انصراف') {
    await clearState(message.from.id);
    return api.sendMessage({ chat_id: message.chat.id, text: 'بازگشت به منوی ادمین.', reply_markup: ADMIN_MENU });
  }
  let user;
  if (/^\d{5,}$/.test(text)) user = await getUserByTelegramId(parseInt(text, 10));
  else user = await getUserByPhone(text.replace(/\D/g, ''));
  if (!user) return api.sendMessage({ chat_id: message.chat.id, text: '❌ کاربری یافت نشد.' });
  await showUserDetailById(message.chat.id, user.telegramId);
}

export async function userDetailCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const targetId = parseInt(callback.data.split(':')[1], 10);
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await showUserDetailById(callback.message.chat.id, targetId);
}

export async function showUserDetailById(chatId, targetId) {
  const user = await getUserByTelegramId(targetId);
  if (!user) return api.sendMessage({ chat_id: chatId, text: '❌ کاربر یافت نشد.' });
  const configs = await listConfigsByUser(targetId);
  const totalApproved = await sumApprovedByUser(targetId);
  const text = `👤 **کاربر \`${targetId}\`**\n` +
    `📞 ${formatPhoneAdmin(user.phone)} ${user.phoneVerified ? '✅' : '❌'}\n` +
    `💰 کیف پول: \`${formatNumber(user.wallet || 0)}\`\n` +
    `🛒 مجموع خرید تایید شده: \`${formatNumber(totalApproved)}\`\n` +
    `🏷 رتبه: \`${user.rank}\`\n` +
    `🔗 کد معرف: \`${user.referralCode}\`\n` +
    `👥 زیرمجموعه از: \`${user.referredBy || '-'}\`\n` +
    `📦 تعداد کانفیگ: \`${configs.length}\`\n` +
    `🚦 وضعیت: ${user.isBlocked ? '⛔ مسدود' : '✅ فعال'}`;
  const kb = {
    inline_keyboard: [
      [{ text: user.isBlocked ? '✅ رفع مسدودیت' : '⛔ مسدود کردن', callback_data: `toggle_block:${targetId}` }],
      [{ text: '💰 افزودن/کسر موجودی', callback_data: `edit_balance:${targetId}` }],
      [{ text: '🔄 ریست کول‌داون تست', callback_data: `reset_test:${targetId}` }],
    ],
  };
  await api.sendMessage({ chat_id: chatId, text, reply_markup: kb, parse_mode: 'Markdown' });
}

export async function toggleBlockCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const targetId = parseInt(callback.data.split(':')[1], 10);
  const user = await getUserByTelegramId(targetId);
  if (!user) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await updateUser(targetId, { isBlocked: !user.isBlocked });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: user.isBlocked ? '✅ رفع مسدودیت شد' : '⛔ مسدود شد' });
  await showUserDetailById(callback.message.chat.id, targetId);
}

export async function editBalanceCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const targetId = parseInt(callback.data.split(':')[1], 10);
  await setState(callback.from.id, 'admin:user_balance', { targetId });
  await api.sendMessage({
    chat_id: callback.message.chat.id,
    text: `💰 مبلغ تغییر موجودی کاربر \`${targetId}\` را وارد کنید.\nبرای افزودن عدد مثبت و برای کسر عدد منفی (مثلاً \`-5000\`).`,
    parse_mode: 'Markdown', reply_markup: CANCEL_MENU,
  });
  await api.answerCallbackQuery({ callback_query_id: callback.id });
}

export async function processBalanceEdit(message) {
  if (message.text === '❌ انصراف') {
    await clearState(message.from.id);
    return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU });
  }
  const state = await getState(message.from.id);
  const { targetId } = state.data;
  const delta = parseInt((message.text || '').trim(), 10);
  if (Number.isNaN(delta)) return api.sendMessage({ chat_id: message.chat.id, text: '❌ عدد نامعتبر.' });
  const user = await getUserByTelegramId(targetId);
  if (!user) { await clearState(message.from.id); return api.sendMessage({ chat_id: message.chat.id, text: '❌ کاربر یافت نشد.' }); }
  const newWallet = Math.max(0, (user.wallet || 0) + delta);
  await updateUser(targetId, { wallet: newWallet });
  await clearState(message.from.id);
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ موجودی کاربر \`${targetId}\` به \`${formatNumber(newWallet)}\` تغییر یافت.`, parse_mode: 'Markdown', reply_markup: ADMIN_MENU });
  try { await api.sendMessage({ chat_id: targetId, text: `💰 موجودی کیف پول شما توسط ادمین ${delta >= 0 ? 'افزایش' : 'کاهش'} یافت.\nموجودی فعلی: \`${formatNumber(newWallet)}\` تومان`, parse_mode: 'Markdown' }); } catch { /* ignore */ }
}

export async function resetTestCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const targetId = parseInt(callback.data.split(':')[1], 10);
  await updateUser(targetId, { lastTestTime: null });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '✅ کول‌داون تست ریست شد' });
}
