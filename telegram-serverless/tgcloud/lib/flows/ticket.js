// Port of bot/handlers/ticket.py — user side of the support ticket system.
import { api } from 'sdk';
import { setState, getState, clearState } from '../state.js';
import { TICKET_MENU, CANCEL_MENU, BACK_MENU, MAIN_MENU } from '../keyboards.js';
import {
  createTicket, getTicketById, listTicketsByUser, listOpenTicketsByUser,
  updateTicket, createTicketMessage, listMessagesByTicket,
} from '../db/tickets.js';
import { getAllAdminIds } from '../auth.js';
import { escapeHtml } from '../helpers.js';

const STATUS_LABEL = { open: '🟢 باز', admin_replied: '💬 پاسخ داده شده', closed: '🔒 بسته شده' };
const MAX_OPEN_TICKETS = 3;

export async function showTicketMenu(message) {
  await api.sendMessage({ chat_id: message.chat.id, text: '🎫 **پشتیبانی**\nیک گزینه را انتخاب کنید:', reply_markup: TICKET_MENU, parse_mode: 'Markdown' });
}

export async function newTicketStart(message) {
  const telegramId = message.from.id;
  const openTickets = await listOpenTicketsByUser(telegramId);
  if (openTickets.length >= MAX_OPEN_TICKETS) {
    return api.sendMessage({ chat_id: message.chat.id, text: `⚠️ شما حداکثر ${MAX_OPEN_TICKETS} تیکت باز می‌توانید داشته باشید. لطفاً منتظر پاسخ یا بستن تیکت‌های قبلی بمانید.`, reply_markup: TICKET_MENU });
  }
  await setState(telegramId, 'ticket:waiting_subject', {});
  await api.sendMessage({ chat_id: message.chat.id, text: '📝 موضوع تیکت خود را در یک خط وارد کنید:', reply_markup: CANCEL_MENU });
}

export async function processSubject(message) {
  const telegramId = message.from.id;
  if (message.text === '❌ انصراف') return cancelTicketFlow(message);
  const subject = (message.text || '').trim().slice(0, 100);
  if (!subject) return api.sendMessage({ chat_id: message.chat.id, text: '❌ موضوع نامعتبر. دوباره وارد کنید:' });
  await setState(telegramId, 'ticket:waiting_message', { subject });
  await api.sendMessage({ chat_id: message.chat.id, text: '✍️ متن پیام خود را بنویسید (می‌توانید عکس هم ارسال کنید):', reply_markup: CANCEL_MENU });
}

export async function processFirstMessage(message) {
  const telegramId = message.from.id;
  if (message.text === '❌ انصراف') return cancelTicketFlow(message);
  const state = await getState(telegramId);
  const subject = state?.data?.subject || 'بدون موضوع';
  const text = message.text || message.caption || null;
  const photoFileId = message.photo ? message.photo[message.photo.length - 1].file_id : null;
  if (!text && !photoFileId) return api.sendMessage({ chat_id: message.chat.id, text: '❌ لطفاً متن یا عکس ارسال کنید.' });

  const ticket = await createTicket({ telegramId, subject, status: 'open' });
  await createTicketMessage({ ticketId: ticket.id, senderId: telegramId, senderType: 'user', text, photoFileId });
  await clearState(telegramId);
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ تیکت شما با شماره #${ticket.id} ثبت شد. منتظر پاسخ پشتیبانی باشید.`, reply_markup: MAIN_MENU });

  const adminIds = await getAllAdminIds();
  const notify = `🎫 **تیکت جدید #${ticket.id}**\n👤 \`${telegramId}\`\n📝 ${escapeHtml(subject)}\n\n${escapeHtml(text || '🖼 (عکس)')}`;
  const kb = { inline_keyboard: [[{ text: '💬 پاسخ', callback_data: `admin_reply_ticket:${ticket.id}` }]] };
  for (const adminId of adminIds) {
    try {
      if (photoFileId) await api.sendPhoto({ chat_id: adminId, photo: photoFileId, caption: notify, parse_mode: 'Markdown', reply_markup: kb });
      else await api.sendMessage({ chat_id: adminId, text: notify, parse_mode: 'Markdown', reply_markup: kb });
    } catch { /* admin unreachable */ }
  }
}

async function cancelTicketFlow(message) {
  await clearState(message.from.id);
  await api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: TICKET_MENU });
}

export async function myTickets(message) {
  const tks = await listTicketsByUser(message.from.id);
  if (!tks.length) return api.sendMessage({ chat_id: message.chat.id, text: '📋 شما هنوز تیکتی ثبت نکرده‌اید.', reply_markup: TICKET_MENU });
  const rows = tks.map((t) => [{ text: `#${t.id} ${t.subject} — ${STATUS_LABEL[t.status] || t.status}`, callback_data: `view_ticket:${t.id}` }]);
  await api.sendMessage({ chat_id: message.chat.id, text: '📋 **تیکت‌های شما:**', reply_markup: { inline_keyboard: rows }, parse_mode: 'Markdown' });
}

export async function viewTicket(callback) {
  const ticketId = parseInt(callback.data.split(':')[1], 10);
  const ticket = await getTicketById(ticketId);
  if (!ticket || ticket.telegramId !== callback.from.id) {
    return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'دسترسی ندارید', show_alert: true });
  }
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
  const msgs = await listMessagesByTicket(ticketId);
  let text = `🎫 **تیکت #${ticket.id} — ${ticket.subject}**\nوضعیت: ${STATUS_LABEL[ticket.status] || ticket.status}\n\n`;
  for (const m of msgs) {
    const who = m.senderType === 'admin' ? '👮 پشتیبانی' : '👤 شما';
    text += `${who}: ${m.text || '🖼 (عکس)'}\n`;
  }
  const rows = [];
  if (ticket.status !== 'closed') {
    rows.push([{ text: '✍️ پاسخ', callback_data: `reply_ticket:${ticket.id}` }]);
    rows.push([{ text: '🔒 بستن تیکت', callback_data: `close_ticket:${ticket.id}` }]);
  }
  rows.push([{ text: '🔙 بازگشت', callback_data: 'my_tickets_back' }]);
  await api.sendMessage({ chat_id: callback.message.chat.id, text, reply_markup: { inline_keyboard: rows }, parse_mode: 'Markdown' });
}

export async function replyTicketStart(callback) {
  const ticketId = parseInt(callback.data.split(':')[1], 10);
  const ticket = await getTicketById(ticketId);
  if (!ticket || ticket.telegramId !== callback.from.id || ticket.status === 'closed') {
    return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'امکان‌پذیر نیست', show_alert: true });
  }
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
  await setState(callback.from.id, 'ticket:waiting_reply', { ticketId });
  await api.sendMessage({ chat_id: callback.message.chat.id, text: '✍️ پاسخ خود را بنویسید:', reply_markup: CANCEL_MENU });
}

export async function processUserReply(message) {
  const telegramId = message.from.id;
  if (message.text === '❌ انصراف') return cancelTicketFlow(message);
  const state = await getState(telegramId);
  const ticketId = state?.data?.ticketId;
  const ticket = ticketId ? await getTicketById(ticketId) : null;
  if (!ticket) { await clearState(telegramId); return api.sendMessage({ chat_id: message.chat.id, text: '❌ تیکت یافت نشد.', reply_markup: MAIN_MENU }); }
  const text = message.text || message.caption || null;
  const photoFileId = message.photo ? message.photo[message.photo.length - 1].file_id : null;
  if (!text && !photoFileId) return api.sendMessage({ chat_id: message.chat.id, text: '❌ لطفاً متن یا عکس ارسال کنید.' });

  await createTicketMessage({ ticketId, senderId: telegramId, senderType: 'user', text, photoFileId });
  await updateTicket(ticketId, { status: 'open' });
  await clearState(telegramId);
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ پاسخ شما به تیکت #${ticketId} ثبت شد.`, reply_markup: MAIN_MENU });

  const adminIds = await getAllAdminIds();
  const notify = `💬 **پاسخ کاربر به تیکت #${ticketId}**\n👤 \`${telegramId}\`\n\n${escapeHtml(text || '🖼 (عکس)')}`;
  const kb = { inline_keyboard: [[{ text: '💬 پاسخ', callback_data: `admin_reply_ticket:${ticketId}` }]] };
  for (const adminId of adminIds) {
    try {
      if (photoFileId) await api.sendPhoto({ chat_id: adminId, photo: photoFileId, caption: notify, parse_mode: 'Markdown', reply_markup: kb });
      else await api.sendMessage({ chat_id: adminId, text: notify, parse_mode: 'Markdown', reply_markup: kb });
    } catch { /* ignore */ }
  }
}

export async function closeTicketUser(callback) {
  const ticketId = parseInt(callback.data.split(':')[1], 10);
  const ticket = await getTicketById(ticketId);
  if (!ticket || ticket.telegramId !== callback.from.id) {
    return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'دسترسی ندارید', show_alert: true });
  }
  await updateTicket(ticketId, { status: 'closed' });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '✅ تیکت بسته شد' });
  await api.editMessageText({ chat_id: callback.message.chat.id, message_id: callback.message.message_id, text: `🎫 تیکت #${ticketId} بسته شد.` });
}

export async function myTicketsBack(callback) {
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
  await api.sendMessage({ chat_id: callback.message.chat.id, text: '🎫 **پشتیبانی**', reply_markup: TICKET_MENU, parse_mode: 'Markdown' });
}
