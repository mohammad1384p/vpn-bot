// Port of bot/handlers/packages.py
import { api } from 'sdk';
import { getUserByTelegramId } from '../db/users.js';
import { listActivePackages, getPackageById } from '../db/packages.js';
import { requiresPhoneAuth } from './start.js';
import { PHONE_KB } from '../keyboards.js';
import { setState, updateStateData } from '../state.js';
import { formatNumber } from '../helpers.js';

export async function showPackages(message) {
  const chatId = message.chat.id;
  const telegramId = message.from.id;
  const user = await getUserByTelegramId(telegramId);
  if (!user) return api.sendMessage({ chat_id: chatId, text: '⚠️ لطفاً ابتدا /start را بزنید.' });
  if (requiresPhoneAuth(user)) {
    return api.sendMessage({ chat_id: chatId, text: '🔐 چون با لینک زیرمجموعه وارد شده‌اید، برای خرید کانفیگ ابتدا شماره تماس خود را تایید کنید.', reply_markup: PHONE_KB });
  }
  const pkgs = await listActivePackages();
  if (!pkgs.length) {
    await api.sendMessage({ chat_id: chatId, text: '⚠️ بسته‌ای تعریف نشده. مبلغ دلخواه را وارد کنید:' });
    await setState(telegramId, 'payment:waiting_for_amount', {});
    return;
  }
  let text = '🛒 **بسته‌های موجود:**\n';
  const kbButtons = [];
  for (const pkg of pkgs) {
    const vol = pkg.volumeGb <= 0 ? '♾️ نامحدود' : `${pkg.volumeGb}GB`;
    const dur = pkg.durationDays <= 0 ? '♾️ نامحدود' : `${pkg.durationDays}d`;
    const label = `${pkg.name} | 📦 ${vol} | ⏱ ${dur} | 💰 ${formatNumber(pkg.price)}T`;
    kbButtons.push([{ text: label, callback_data: `select_pkg:${pkg.id}` }]);
  }
  kbButtons.push([{ text: '✍️ مبلغ دلخواه', callback_data: 'custom_amount' }]);
  await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kbButtons }, parse_mode: 'Markdown' });
}

export async function selectPackage(callback) {
  const pkgId = parseInt(callback.data.split(':')[1], 10);
  const pkg = await getPackageById(pkgId);
  if (!pkg) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
  // Not actually waiting for a text reply yet (next step is a button) — use a
  // neutral step name so a stray text message isn't misrouted as an amount.
  await setState(callback.from.id, 'payment:cart', {
    amount: pkg.price, packageId: pkg.id, packageName: pkg.name, volumeGb: pkg.volumeGb, durationDays: pkg.durationDays,
  });
  const kb = { inline_keyboard: [
    [{ text: '🎟 اعمال کد تخفیف', callback_data: 'apply_discount_purchase' }],
    [{ text: '➡️ ادامه و پرداخت', callback_data: 'skip_discount_purchase' }],
  ] };
  await api.editMessageText({
    chat_id: callback.message.chat.id, message_id: callback.message.message_id,
    text: `📦 **بسته انتخابی:** ${pkg.name}\n💰 **قیمت:** \`${formatNumber(pkg.price)}\` تومان\n\nآیا کد تخفیف دارید؟`,
    reply_markup: kb, parse_mode: 'Markdown',
  });
}

export async function customAmount(callback) {
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
  try { await api.deleteMessage({ chat_id: callback.message.chat.id, message_id: callback.message.message_id }); } catch { /* ignore */ }
  await api.sendMessage({ chat_id: callback.message.chat.id, text: '✍️ مبلغ دلخواه (تومان):' });
  await setState(callback.from.id, 'payment:waiting_for_amount', {});
}
