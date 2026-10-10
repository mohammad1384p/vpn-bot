// Port of bot/handlers/payment.py (manual card-to-card purchase payment flow)
import { api } from 'sdk';
import { getState, setState, updateStateData, clearState } from '../state.js';
import { getSetting } from '../db/settings.js';
import { validateDiscountCode, incrementUsage } from '../db/discounts.js';
import { createPayment, countApprovedByUser } from '../db/payments.js';
import { getAllAdminIds, getSuperAdminId } from '../auth.js';
import { MAIN_MENU } from '../keyboards.js';
import { formatNumber } from '../helpers.js';

export async function showCardInfo(chatId, telegramId, amount) {
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
    await updateStateData(telegramId, { discountAmount: discountValue, finalAmount });
  } else {
    await updateStateData(telegramId, { discountAmount: 0, finalAmount: amount });
  }

  const cardNum = await getSetting('card_number', '');
  const cardName = await getSetting('card_name', '');
  if (!cardNum) {
    await api.sendMessage({ chat_id: chatId, text: '❌ شماره کارت تنظیم نشده.' });
    await clearState(telegramId);
    return;
  }

  let text = `💳 **پرداخت:**\n💰 مبلغ اصلی: \`${formatNumber(amount)}\` T\n`;
  if (discountCode && amount >= minAmount) {
    text += `🎟 تخفیف \`${discountCode}\`: -\`${formatNumber(discountValue)}\` T\n✅ **مبلغ نهایی: \`${formatNumber(finalAmount)}\` T**\n`;
  }
  text += `💳 \`${cardNum}\`\n👤 ${cardName || 'نامشخص'}\n📸 عکس رسید را ارسال کنید.`;
  await api.sendMessage({ chat_id: chatId, text, parse_mode: 'Markdown', reply_markup: { remove_keyboard: true } });
  const finalData = await updateStateData(telegramId, { amount: finalAmount });
  await setState(telegramId, 'payment:waiting_for_receipt', finalData);
}

export async function processAmount(message) {
  const text = (message.text || '').trim();
  if (!/^\d+$/.test(text)) return;
  const amount = parseInt(text, 10);
  if (amount < 10000) return api.sendMessage({ chat_id: message.chat.id, text: '❌ حداقل ۱۰,۰۰۰ تومان.' });
  await updateStateData(message.from.id, { amount, packageName: 'سفارش اختصاصی' });
  const kb = { inline_keyboard: [
    [{ text: '🎟 اعمال کد تخفیف', callback_data: 'apply_discount_purchase' }],
    [{ text: '➡️ ادامه و پرداخت', callback_data: 'skip_discount_purchase' }],
  ] };
  await api.sendMessage({ chat_id: message.chat.id, text: `💰 **مبلغ وارد شده:** \`${formatNumber(amount)}\` تومان\n\nآیا کد تخفیف دارید؟`, reply_markup: kb, parse_mode: 'Markdown' });
}

export async function skipDiscountPurchase(callback) {
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
  const state = await getState(callback.from.id);
  await showCardInfo(callback.message.chat.id, callback.from.id, state.data.amount);
}

export async function applyDiscountPurchase(callback) {
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
  await api.editMessageText({ chat_id: callback.message.chat.id, message_id: callback.message.message_id, text: '🎟 لطفاً کد تخفیف خود را ارسال کنید (یا /cancel):' });
  await setState(callback.from.id, 'payment:waiting_for_discount_code', (await getState(callback.from.id)).data);
}

export async function processDiscountCode(message) {
  const telegramId = message.from.id;
  const state = await getState(telegramId);
  if (message.text === '/cancel') {
    return showCardInfo(message.chat.id, telegramId, state.data.amount);
  }
  const code = (message.text || '').trim().toUpperCase();
  const approvedCount = await countApprovedByUser(telegramId);
  const result = await validateDiscountCode(code, state.data.amount, { forRenewal: false, hasApprovedPayment: approvedCount > 0 });
  if (!result.ok) return api.sendMessage({ chat_id: message.chat.id, text: result.error, parse_mode: 'Markdown' });
  await updateStateData(telegramId, { discountCode: code, discountPercent: result.dc.percent, minAmount: result.dc.minAmount });
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ کد تخفیف \`${result.dc.percent}%\` اعمال شد!`, parse_mode: 'Markdown' });
  await showCardInfo(message.chat.id, telegramId, state.data.amount);
}

export async function processReceipt(message) {
  const telegramId = message.from.id;
  if (!message.photo || !message.photo.length) {
    return api.sendMessage({ chat_id: message.chat.id, text: '❌ لطفاً عکس رسید پرداخت را ارسال کنید.' });
  }
  const photo = message.photo[message.photo.length - 1];
  if (photo.file_size && photo.file_size > 5 * 1024 * 1024) {
    return api.sendMessage({ chat_id: message.chat.id, text: '❌ حجم عکس بالاست.' });
  }
  const state = await getState(telegramId);
  const data = state?.data || {};
  const amount = data.finalAmount ?? data.amount;
  const packageId = data.packageId || null;
  const packageName = data.packageName || 'سفارش اختصاصی';
  const discountCode = data.discountCode;
  const discountAmount = data.discountAmount || 0;

  if (discountCode) {
    const { getDiscountByCode } = await import('../db/discounts.js');
    const dc = await getDiscountByCode(discountCode);
    if (dc) await incrementUsage(dc.id, dc.usedCount);
  }
  const payment = await createPayment({ telegramId, amount, status: 'pending', packageId, discountCode, discountAmount });

  await clearState(telegramId);
  await api.sendMessage({ chat_id: message.chat.id, text: '✅ رسید ثبت شد. در انتظار تایید.', reply_markup: MAIN_MENU });

  const superAdminId = await getSuperAdminId();
  const adminIds = await getAllAdminIds();
  let forwardedMsgId = null;
  if (superAdminId) {
    try {
      const fwd = await api.forwardMessage({ chat_id: superAdminId, from_chat_id: message.chat.id, message_id: message.message_id });
      forwardedMsgId = fwd.message_id;
    } catch { /* ignore */ }
  }
  const kb = { inline_keyboard: [
    [{ text: '✅ تایید', callback_data: `approve_pay_${payment.id}` }],
    [{ text: '❌ رد', callback_data: `reject_pay_${payment.id}` }],
  ] };
  const pkgInfo = packageId ? `📦 \`${packageName}\`` : '✍️ سفارش اختصاصی';
  const discountInfo = discountCode ? `\n🎟 \`${discountCode}\`: -${formatNumber(discountAmount)}T` : '';
  const msgText = `🔔 **پرداخت جدید**\n${pkgInfo}${discountInfo}\n👤 \`${telegramId}\`\n💰 \`${formatNumber(amount)}\` T\n🆔 \`${payment.id}\``;

  for (const adminId of adminIds) {
    try {
      await api.sendMessage({
        chat_id: adminId, text: msgText,
        reply_to_message_id: adminId === superAdminId ? forwardedMsgId : undefined,
        reply_markup: kb, parse_mode: 'Markdown',
      });
      if (adminId !== superAdminId) {
        await api.forwardMessage({ chat_id: adminId, from_chat_id: message.chat.id, message_id: message.message_id });
      }
    } catch { /* admin may have blocked the bot */ }
  }
}
