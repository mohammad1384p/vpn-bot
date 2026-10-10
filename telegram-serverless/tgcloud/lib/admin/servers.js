// Port of the multi-server management part of bot/handlers/config_settings.py.
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import { listServers, getServerById, createServer, updateServer, deleteServer } from '../db/servers.js';
import { testServerConnection } from '../panel.js';
import { setState, getState, clearState } from '../state.js';
import { ADMIN_MENU, CANCEL_MENU } from '../keyboards.js';

async function renderServersMenu(chatId) {
  const rows = await listServers();
  let text = '🖥 **سرورهای پنل**\n';
  const kb = [];
  for (const s of rows) {
    text += `${s.isActive ? '✅' : '⛔'} \`${s.id}\` ${s.name} (priority ${s.priority})\n`;
    kb.push([{ text: `✏️ ${s.name}`, callback_data: `server_detail:${s.id}` }]);
  }
  kb.push([{ text: '➕ افزودن سرور', callback_data: 'server_add' }]);
  await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kb }, parse_mode: 'Markdown' });
}

// Entry point from the "🖥 مدیریت سرورها" inline button in settings.js.
export async function serversMenu(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await renderServersMenu(callback.message.chat.id);
}

async function renderServerDetail(chatId, id) {
  const s = await getServerById(id);
  if (!s) return api.sendMessage({ chat_id: chatId, text: '❌ یافت نشد.' });
  const text = `🖥 **${s.name}**\n🌐 \`${s.url}\`\n🔑 \`${s.apiKey.slice(0, 6)}...\`\n🔢 اولویت: ${s.priority}\n🚦 ${s.isActive ? 'فعال' : 'غیرفعال'}`;
  const kb = {
    inline_keyboard: [
      [{ text: '🔌 تست اتصال', callback_data: `server_test:${id}` }],
      [{ text: s.isActive ? '⛔ غیرفعال کردن' : '✅ فعال کردن', callback_data: `server_toggle:${id}` }],
      [{ text: '🗑 حذف', callback_data: `server_delete:${id}` }],
    ],
  };
  await api.sendMessage({ chat_id: chatId, text, reply_markup: kb, parse_mode: 'Markdown' });
}

export async function serverDetailCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  const s = await getServerById(id);
  if (!s) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await renderServerDetail(callback.message.chat.id, id);
}

export async function serverTestCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  const s = await getServerById(id);
  if (!s) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '⏳ در حال تست...' });
  const result = await testServerConnection(s.url, s.apiKey);
  await api.sendMessage({ chat_id: callback.message.chat.id, text: result.success ? `✅ اتصال موفق بود. (${result.count} اینباند)` : `❌ اتصال ناموفق: ${result.msg}` });
}

export async function serverToggleCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  const s = await getServerById(id);
  if (!s) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await updateServer(id, { isActive: !s.isActive });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '✅ به‌روزرسانی شد' });
  await renderServerDetail(callback.message.chat.id, id);
}

export async function serverDeleteCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  await deleteServer(id);
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '🗑 حذف شد' });
  await renderServersMenu(callback.message.chat.id);
}

export async function serverAddCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  await setState(callback.from.id, 'admin:server_add', {});
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await api.sendMessage({
    chat_id: callback.message.chat.id,
    text: '➕ اطلاعات سرور جدید را در ۴ خط ارسال کنید:\n`نام`\n`آدرس پنل (https://...)`\n`API Key`\n`اولویت (عدد، کوچکتر = اول)`\n\nمثال:\n`سرور آلمان`\n`https://panel.example.com:54321`\n`xxxxx-api-key`\n`1`',
    parse_mode: 'Markdown', reply_markup: CANCEL_MENU,
  });
}

export async function processServerAdd(message) {
  if (message.text === '❌ انصراف') {
    await clearState(message.from.id);
    return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU });
  }
  const lines = (message.text || '').trim().split('\n').map((l) => l.trim()).filter(Boolean);
  if (lines.length < 4) {
    return api.sendMessage({ chat_id: message.chat.id, text: '❌ باید دقیقاً ۴ خط ارسال کنید (نام، آدرس، کلید، اولویت).' });
  }
  const [name, url, apiKey, priorityStr] = lines;
  const priority = parseInt(priorityStr, 10) || 1;
  await createServer({ name, url, apiKey, priority, isActive: true });
  await clearState(message.from.id);
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ سرور \`${name}\` اضافه شد.`, parse_mode: 'Markdown', reply_markup: ADMIN_MENU });
}
