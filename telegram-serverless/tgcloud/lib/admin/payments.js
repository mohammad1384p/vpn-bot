// Port of the payment-approval half of bot/handlers/admin.py.
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import { getPaymentById, updatePayment } from '../db/payments.js';
import { getPackageById } from '../db/packages.js';
import { getUserByTelegramId, updateUser } from '../db/users.js';
import { addClient } from '../panel.js';
import { sendConfigPackage } from '../sendConfig.js';
import { setState, getState, clearState } from '../state.js';
import { formatNumber, uuidv4 } from '../helpers.js';
import { MAIN_MENU } from '../keyboards.js';

async function appendToCallbackMessage(callback, suffix) {
  try {
    const base = callback.message.text || callback.message.caption || '';
    await api.editMessageText({ chat_id: callback.message.chat.id, message_id: callback.message.message_id, text: `${base}\n${suffix}` });
  } catch { /* message may be a photo/forward without editable text */ }
}

export async function approvePayment(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const paymentId = parseInt(callback.data.split('_').pop(), 10);
  const payment = await getPaymentById(paymentId);
  if (!payment || payment.status !== 'pending') {
    await api.answerCallbackQuery({ callback_query_id: callback.id, text: '❌ این پرداخت قبلاً پردازش شده.', show_alert: true });
    return;
  }
  if (payment.packageId) {
    try { await api.answerCallbackQuery({ callback_query_id: callback.id, text: '⏳ در حال صدور کانفیگ...' }); } catch { /* ignore */ }
    await issueConfigForPayment(callback, payment, await getPackageById(payment.packageId));
    return;
  }
  // Custom amount — volume/duration were never chosen up front, ask the admin now.
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await setState(callback.from.id, 'admin:approve_custom_payment', { paymentId, chatId: callback.message.chat.id, messageId: callback.message.message_id });
  await api.sendMessage({
    chat_id: callback.from.id,
    text: `📦 حجم و مدت سرویس برای پرداخت #${paymentId} را به صورت \`حجم(GB) مدت(روز)\` ارسال کنید.\nبرای نامحدود از عدد 0 استفاده کنید. مثال: \`20 30\``,
    parse_mode: 'Markdown',
  });
}

export async function processCustomPaymentApproval(message) {
  const state = await getState(message.from.id);
  const { paymentId, chatId, messageId } = state.data;
  const parts = (message.text || '').trim().split(/\s+/);
  const volumeGb = parseInt(parts[0], 10);
  const durationDays = parseInt(parts[1], 10);
  if (Number.isNaN(volumeGb) || Number.isNaN(durationDays)) {
    return api.sendMessage({ chat_id: message.chat.id, text: '❌ فرمت نامعتبر. دوباره به صورت `حجم مدت` ارسال کنید.', parse_mode: 'Markdown' });
  }
  await clearState(message.from.id);
  const payment = await getPaymentById(paymentId);
  if (!payment || payment.status !== 'pending') {
    return api.sendMessage({ chat_id: message.chat.id, text: '❌ این پرداخت قبلاً پردازش شده.' });
  }
  await issueConfigForPayment({ from: message.from, message: { chat: { id: chatId }, message_id: messageId } }, payment, null, { volumeGb, durationDays });
}

async function issueConfigForPayment(callback, payment, pkg, override = null) {
  const volumeGb = override?.volumeGb ?? pkg?.volumeGb ?? 0;
  const durationDays = override?.durationDays ?? pkg?.durationDays ?? 0;
  const unlimitedVolume = volumeGb <= 0;
  const unlimitedTime = durationDays <= 0;
  const username = `user_${payment.telegramId}_${uuidv4().slice(0, 8)}`;

  const result = await addClient({
    email: username, totalGb: volumeGb, expiryHours: durationDays * 24, unlimitedVolume, unlimitedTime,
  });

  if (!result.success) {
    await appendToCallbackMessage(callback, `⚠️ ${result.msg}`);
    try { await api.sendMessage({ chat_id: callback.from.id, text: `❌ ساخت کانفیگ ناموفق بود: ${result.msg}` }); } catch { /* ignore */ }
    return;
  }

  const { createConfig } = await import('../db/configs.js');
  await createConfig({
    telegramId: payment.telegramId, username, subLink: result.subLink, subId: result.subId,
    isActive: true, expiryTime: result.expiryTimeMs || 0, serverId: result.serverId,
    volumeGb, durationDays, isTest: false, isUnlimitedVolume: unlimitedVolume, isUnlimitedTime: unlimitedTime,
  });
  await updatePayment(payment.id, { status: 'approved' });
  const user = await getUserByTelegramId(payment.telegramId);
  if (user) await updateUser(payment.telegramId, { totalSpent: (user.totalSpent || 0) + payment.amount });

  const volDisplay = unlimitedVolume ? '♾️ نامحدود' : `${volumeGb} GB`;
  const durDisplay = unlimitedTime ? '♾️ نامحدود' : `${durationDays} روز`;
  try {
    await sendConfigPackage({ userId: payment.telegramId, subLink: result.subLink, username, volumeDisplay: volDisplay, durationDisplay: durDisplay });
  } catch (e) {
    console.error('issueConfigForPayment send failed', e);
  }
  await appendToCallbackMessage(callback, `✅ تایید شد و کانفیگ برای کاربر ارسال شد.\n💰 \`${formatNumber(payment.amount)}\` T`);
}

export async function rejectPayment(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const paymentId = parseInt(callback.data.split('_').pop(), 10);
  const payment = await getPaymentById(paymentId);
  if (!payment || payment.status !== 'pending') {
    await api.answerCallbackQuery({ callback_query_id: callback.id, text: '❌ این پرداخت قبلاً پردازش شده.', show_alert: true });
    return;
  }
  await updatePayment(paymentId, { status: 'rejected' });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '❌ رد شد' });
  await appendToCallbackMessage(callback, '❌ این پرداخت رد شد.');
  try {
    await api.sendMessage({ chat_id: payment.telegramId, text: '❌ متاسفانه رسید پرداخت شما تایید نشد. برای پیگیری با پشتیبانی در ارتباط باشید.', reply_markup: MAIN_MENU });
  } catch { /* user may have blocked the bot */ }
}
