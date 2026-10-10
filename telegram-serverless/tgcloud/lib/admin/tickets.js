// Port of the admin side of bot/handlers/ticket.py.
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import { listOpenTickets, getTicketById, listMessagesByTicket, createTicketMessage, updateTicket } from '../db/tickets.js';
import { setState, getState, clearState } from '../state.js';
import { ADMIN_MENU, CANCEL_MENU } from '../keyboards.js';
import { escapeHtml } from '../helpers.js';

const STATUS_LABEL = { open: '🟢 باز', admin_replied: '💬 پاسخ داده شده', closed: '🔒 بسته شده' };

export async function ticketsMenu(message) {
  if (!(await isAdmin(message.from.id))) return;
  const tks = await listOpenTickets();
  if (!tks.length) return api.sendMessage({ chat_id: message.chat.id, text: '🎫 تیکت باز وجود ندارد.' });
  const rows = tks.map((t) => [{ text: `#${t.id} ${t.subject} — ${STATUS_LABEL[t.status] || t.status}`, callback_data: `admin_view_ticket:${t.id}` }]);
  await api.sendMessage({ chat_id: message.chat.id, text: '🎫 **تیکت‌های باز:**', reply_markup: { inline_keyboard: rows }, parse_mode: 'Markdown' });
}

async function renderTicketDetail(chatId, ticketId) {
  const ticket = await getTicketById(ticketId);
  if (!ticket) return api.sendMessage({ chat_id: chatId, text: '❌ تیکت یافت نشد.' });
  const msgs = await listMessagesByTicket(ticketId);
  let text = `🎫 **تیکت #${ticket.id} — ${ticket.subject}**\n👤 کاربر: \`${ticket.telegramId}\`\nوضعیت: ${STATUS_LABEL[ticket.status] || ticket.status}\n\n`;
  for (const m of msgs) {
    const who = m.senderType === 'admin' ? '👮 پشتیبانی' : '👤 کاربر';
    text += `${who}: ${m.text || '🖼 (عکس)'}\n`;
  }
  const kb = { inline_keyboard: [] };
  if (ticket.status !== 'closed') {
    kb.inline_keyboard.push([{ text: '💬 پاسخ', callback_data: `admin_reply_ticket:${ticket.id}` }]);
    kb.inline_keyboard.push([{ text: '🔒 بستن تیکت', callback_data: `admin_close_ticket:${ticket.id}` }]);
  }
  await api.sendMessage({ chat_id: chatId, text, reply_markup: kb, parse_mode: 'Markdown' });
}

export async function adminViewTicketCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const ticketId = parseInt(callback.data.split(':')[1], 10);
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await renderTicketDetail(callback.message.chat.id, ticketId);
}

export async function adminReplyTicketStart(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const ticketId = parseInt(callback.data.split(':')[1], 10);
  const ticket = await getTicketById(ticketId);
  if (!ticket || ticket.status === 'closed') {
    return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'امکان‌پذیر نیست', show_alert: true });
  }
  await setState(callback.from.id, 'admin:ticket_reply', { ticketId });
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await api.sendMessage({ chat_id: callback.message.chat.id, text: '✍️ پاسخ خود را بنویسید:', reply_markup: CANCEL_MENU });
}

export async function processAdminTicketReply(message) {
  if (message.text === '❌ انصراف') {
    await clearState(message.from.id);
    return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU });
  }
  const state = await getState(message.from.id);
  const { ticketId } = state.data;
  const ticket = await getTicketById(ticketId);
  if (!ticket) { await clearState(message.from.id); return api.sendMessage({ chat_id: message.chat.id, text: '❌ تیکت یافت نشد.' }); }
  const text = message.text || message.caption || null;
  const photoFileId = message.photo ? message.photo[message.photo.length - 1].file_id : null;
  if (!text && !photoFileId) return api.sendMessage({ chat_id: message.chat.id, text: '❌ لطفاً متن یا عکس ارسال کنید.' });

  await createTicketMessage({ ticketId, senderId: message.from.id, senderType: 'admin', text, photoFileId });
  await updateTicket(ticketId, { status: 'admin_replied' });
  await clearState(message.from.id);
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ پاسخ شما به تیکت #${ticketId} ارسال شد.`, reply_markup: ADMIN_MENU });

  const notify = `💬 **پاسخ پشتیبانی به تیکت #${ticketId}**\n\n${escapeHtml(text || '🖼 (عکس)')}`;
  const kb = { inline_keyboard: [[{ text: '✍️ پاسخ', callback_data: `reply_ticket:${ticketId}` }]] };
  try {
    if (photoFileId) await api.sendPhoto({ chat_id: ticket.telegramId, photo: photoFileId, caption: notify, parse_mode: 'Markdown', reply_markup: kb });
    else await api.sendMessage({ chat_id: ticket.telegramId, text: notify, parse_mode: 'Markdown', reply_markup: kb });
  } catch { /* user may have blocked the bot */ }
}

export async function adminCloseTicketCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const ticketId = parseInt(callback.data.split(':')[1], 10);
  const ticket = await getTicketById(ticketId);
  if (!ticket) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await updateTicket(ticketId, { status: 'closed' });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '✅ بسته شد' });
  try { await api.sendMessage({ chat_id: ticket.telegramId, text: `🔒 تیکت #${ticketId} توسط پشتیبانی بسته شد.` }); } catch { /* ignore */ }
}
