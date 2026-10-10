// Port of bot/handlers/renew.py
import { api } from 'sdk';
import { getState, setState, updateStateData, clearState } from '../state.js';
import { getSetting } from '../db/settings.js';
import { listRenewableConfigs, getConfigById, updateConfig } from '../db/configs.js';
import { findMatchingPackage } from '../db/packages.js';
import { validateDiscountCode, getDiscountByCode, incrementUsage } from '../db/discounts.js';
import { createPayment, getPaymentById, updatePayment } from '../db/payments.js';
import { getAllAdminIds, getSuperAdminId, isAdmin } from '../auth.js';
import { MAIN_MENU, CANCEL_MENU } from '../keyboards.js';
import { formatNumber } from '../helpers.js';
import { renewClient } from '../panel.js';
import { sendConfigPackage } from '../sendConfig.js';

export async function renewMenu(message) {
  const chatId = message.chat.id;
  const telegramId = message.from.id;
  const { getUserByTelegramId } = await import('../db/users.js');
  const { requiresPhoneAuth } = await import('./start.js');
  const { PHONE_KB } = await import('../keyboards.js');
  const user = await getUserByTelegramId(telegramId);
  if (!user) return api.sendMessage({ chat_id: chatId, text: '⚠️ لطفاً ابتدا /start را بزنید.' });
  if (requiresPhoneAuth(user)) {
    return api.sendMessage({ chat_id: chatId, text: '🔐 چون با لینک زیرمجموعه وارد شده‌اید، برای تمدید ابتدا شماره تماس خود را تایید کنید.', reply_markup: PHONE_KB });
  }
  const cfgs = await listRenewableConfigs(telegramId);
  if (!cfgs.length) {
    return api.sendMessage({
      chat_id: chatId, text: '❌ **کانفیگی برای تمدید ندارید.**',
      reply_markup: { keyboard: [[{ text: '🛒 خرید کانفیگ' }], [{ text: '🔙 بازگشت به منو' }]], resize_keyboard: true },
      parse_mode: 'Markdown',
    });
  }
  let text = '🔄 **قابل تمدید:**\n';
  const kbButtons = [];
  for (const c of cfgs) {
    let expiryDisplay;
    if (c.isUnlimitedTime) expiryDisplay = '♾️';
    else {
      const expiryDays = c.expiryTime ? Math.max(0, Math.floor((c.expiryTime - Date.now()) / 86400000)) : 0;
      expiryDisplay = `${expiryDays}d`;
    }
    const vol = c.isUnlimitedVolume ? '♾️' : `${c.volumeGb}GB`;
    kbButtons.push([{ text: `🔗 ${c.username} | ${vol} | ${expiryDisplay}`, callback_data: `select_renew:${c.id}` }]);
  }
  await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kbButtons }, parse_mode: 'Markdown' });
}

export async function selectRenew(callback) {
  const configId = parseInt(callback.data.split(':')[1], 10);
  const config = await getConfigById(configId);
  if (!config || config.telegramId !== callback.from.id) {
    return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'دسترسی ندارید', show_alert: true });
  }
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
  const vol = config.isUnlimitedVolume ? 0 : config.volumeGb;
  const dur = config.isUnlimitedTime ? 0 : config.durationDays;
  const pkg = await findMatchingPackage(vol, dur);
  let renewPrice, pkgNameForDisplay;
  if (pkg) { renewPrice = pkg.price; pkgNameForDisplay = pkg.name; }
  else {
    const v = config.volumeGb > 0 ? config.volumeGb : 10;
    const d = config.durationDays > 0 ? config.durationDays : 30;
    renewPrice = v * 5000 + d * 2000;
    pkgNameForDisplay = 'بسته سفارشی';
  }
  await setState(callback.from.id, 'renew:cart', {
    configId, renewPrice, username: config.username, pkgName: pkgNameForDisplay,
  });
  const kb = { inline_keyboard: [
    [{ text: '🎟 اعمال کد تخفیف', callback_data: 'apply_discount_renew' }],
    [{ text: '➡️ ادامه و پرداخت', callback_data: 'skip_discount_renew' }],
  ] };
  await api.editMessageText({
    chat_id: callback.message.chat.id, message_id: callback.message.message_id,
    text: `🔄 **تمدید سرویس:** \`${config.username}\`\n💰 **هزینه تمدید:** \`${formatNumber(renewPrice)}\` تومان\n\nآیا کد تخفیف دارید؟`,
    reply_markup: kb, parse_mode: 'Markdown',
  });
}

async function showRenewCardInfo(chatId, telegramId, amount) {
  const state = await getState(telegramId);
  const data = state?.data || {};
  const discountCode = data.discountCode;
  const discountPercent = data.discountPercent || 0;
  const minAmount = data.minAmount || 0;
  let finalAmount = amount;
  let discountValue = 0;
  if (discountCode && amount >= minAmount) {
    discountValue = Math.floor((amount * discountPercent) / 100);
    finalAmount = amount - discountValue;
  }
  const cardNum = await getSetting('card_number', '');
  const cardName = await getSetting('card_name', '');
  if (!cardNum) {
    await api.sendMessage({ chat_id: chatId, text: '❌ شماره کارت تنظیم نشده.' });
    await clearState(telegramId);
    return;
  }
  let text = `💳 **پرداخت تمدید:**\n💰 مبلغ اصلی: \`${formatNumber(amount)}\` T\n`;
  if (discountCode && amount >= minAmount) {
    text += `🎟 تخفیف \`${discountCode}\`: -\`${formatNumber(discountValue)}\` T\n✅ **مبلغ نهایی: \`${formatNumber(finalAmount)}\` T**\n`;
  }
  text += `💳 \`${cardNum}\`\n👤 ${cardName || 'نامشخص'}\n📸 عکس رسید را ارسال کنید.`;
  await api.sendMessage({ chat_id: chatId, text, parse_mode: 'Markdown', reply_markup: CANCEL_MENU });
  const finalData = await updateStateData(telegramId, { discountAmount: discountValue, finalAmount, amount: finalAmount });
  await setState(telegramId, 'renew:waiting_for_receipt', finalData);
}

export async function skipDiscountRenew(callback) {
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
  const state = await getState(callback.from.id);
  await showRenewCardInfo(callback.message.chat.id, callback.from.id, state.data.renewPrice);
}

export async function applyDiscountRenew(callback) {
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
  await api.editMessageText({ chat_id: callback.message.chat.id, message_id: callback.message.message_id, text: '🎟 لطفاً کد تخفیف خود را ارسال کنید (یا /cancel):' });
  await setState(callback.from.id, 'renew:waiting_for_discount_code', (await getState(callback.from.id)).data);
}

export async function processDiscountCodeRenew(message) {
  const telegramId = message.from.id;
  const state = await getState(telegramId);
  if (message.text === '/cancel') return showRenewCardInfo(message.chat.id, telegramId, state.data.renewPrice);
  const code = (message.text || '').trim().toUpperCase();
  const result = await validateDiscountCode(code, state.data.renewPrice, { forRenewal: true });
  if (!result.ok) return api.sendMessage({ chat_id: message.chat.id, text: result.error, parse_mode: 'Markdown' });
  await updateStateData(telegramId, { discountCode: code, discountPercent: result.dc.percent, minAmount: result.dc.minAmount });
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ کد تخفیف \`${result.dc.percent}%\` اعمال شد!`, parse_mode: 'Markdown' });
  await showRenewCardInfo(message.chat.id, telegramId, state.data.renewPrice);
}

export async function cancelRenew(message) {
  await clearState(message.from.id);
  await api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: MAIN_MENU });
}

export async function processRenewReceipt(message) {
  const telegramId = message.from.id;
  if (!message.photo || !message.photo.length) {
    return api.sendMessage({ chat_id: message.chat.id, text: '❌ لطفاً عکس رسید پرداخت را ارسال کنید.' });
  }
  const state = await getState(telegramId);
  const data = state?.data || {};
  const { configId, username } = data;
  const amount = data.finalAmount ?? data.renewPrice;
  const discountCode = data.discountCode;
  const discountAmount = data.discountAmount || 0;
  if (discountCode) {
    const dc = await getDiscountByCode(discountCode);
    if (dc) await incrementUsage(dc.id, dc.usedCount);
  }
  const payment = await createPayment({ telegramId, amount, status: 'pending', packageId: null, discountCode, discountAmount });
  await clearState(telegramId);
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ تمدید ثبت شد (#${payment.id}).`, reply_markup: MAIN_MENU });

  const superAdminId = await getSuperAdminId();
  let forwardedMsgId = null;
  if (superAdminId) {
    try {
      const fwd = await api.forwardMessage({ chat_id: superAdminId, from_chat_id: message.chat.id, message_id: message.message_id });
      forwardedMsgId = fwd.message_id;
    } catch { /* ignore */ }
  }
  const kb = { inline_keyboard: [
    [{ text: '✅ تایید', callback_data: `approve_renew_${payment.id}_${configId}` }],
    [{ text: '❌ رد', callback_data: `reject_pay_${payment.id}` }],
  ] };
  const adminIds = await getAllAdminIds();
  const msgText = `🔄 **تمدید**\n👤 \`${telegramId}\`\n🔗 \`${username}\`\n💰 \`${formatNumber(amount)}\` T\n🆔 \`${payment.id}\``;
  for (const adminId of adminIds) {
    try {
      await api.sendMessage({ chat_id: adminId, text: msgText, reply_to_message_id: adminId === superAdminId ? forwardedMsgId : undefined, reply_markup: kb, parse_mode: 'Markdown' });
      if (adminId !== superAdminId) await api.forwardMessage({ chat_id: adminId, from_chat_id: message.chat.id, message_id: message.message_id });
    } catch { /* ignore */ }
  }
}

export async function approveRenew(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  try { await api.answerCallbackQuery({ callback_query_id: callback.id, text: '⏳ در حال تمدید...' }); } catch { /* ignore */ }
  const parts = callback.data.split('_');
  const paymentId = parseInt(parts[2], 10);
  const configId = parseInt(parts[3], 10);

  const payment = await getPaymentById(paymentId);
  const config = await getConfigById(configId);
  if (!payment || payment.status !== 'pending' || !config) {
    try { await api.answerCallbackQuery({ callback_query_id: callback.id, text: 'نامعتبر', show_alert: true }); } catch { /* ignore */ }
    return;
  }
  await updatePayment(paymentId, { status: 'approved' });
  const { username, subLink, telegramId: userTelegramId, volumeGb, durationDays, serverId, isUnlimitedVolume: unlimitedVol, isUnlimitedTime: unlimitedTime } = config;

  try {
    const res = await renewClient({
      email: username, totalGb: unlimitedVol ? 0 : volumeGb, expiryHours: unlimitedTime ? 0 : durationDays * 24,
      serverId, unlimitedVolume: unlimitedVol, unlimitedTime,
    });
    if (res.success) {
      if (res.expiryTimeMs) await updateConfig(configId, { expiryTime: res.expiryTimeMs, isActive: true });
      const volDisplay = unlimitedVol ? '♾️ نامحدود' : `${volumeGb} GB`;
      const durDisplay = unlimitedTime ? '♾️ نامحدود' : `${durationDays} روز`;
      try {
        await sendConfigPackage({ userId: userTelegramId, subLink, username, volumeDisplay: volDisplay, durationDisplay: durDisplay, isRenew: true });
      } catch (e) {
        console.error('approve_renew send failed', e);
        try { await api.sendMessage({ chat_id: userTelegramId, text: `🔄 تمدید انجام شد!\n👤 ${username}\n📦 ${volDisplay}\n⏱ ${durDisplay}\n🔗\n<code>${subLink}</code>`, parse_mode: 'HTML' }); } catch { /* ignore */ }
      }
      try {
        await api.editMessageText({ chat_id: callback.message.chat.id, message_id: callback.message.message_id, text: `${callback.message.text || ''}\n✅ تمدید شد و برای کاربر ارسال شد` });
      } catch { /* ignore */ }
    } else {
      try { await api.editMessageText({ chat_id: callback.message.chat.id, message_id: callback.message.message_id, text: `${callback.message.text || ''}\n⚠️ ${res.msg}` }); } catch { /* ignore */ }
    }
  } catch (e) {
    console.error('approve_renew fatal', e);
    try { await api.editMessageText({ chat_id: callback.message.chat.id, message_id: callback.message.message_id, text: `${callback.message.text || ''}\n❌ خطای داخلی: ${e.message || e}` }); } catch { /* ignore */ }
  }
}
