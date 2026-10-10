// Port of the discount-code CRUD part of bot/handlers/discount.py / admin.py.
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import { listDiscounts, getDiscountById, createDiscount, updateDiscount, deleteDiscount } from '../db/discounts.js';
import { setState, getState, clearState } from '../state.js';
import { ADMIN_MENU, CANCEL_MENU } from '../keyboards.js';

async function renderDiscountsList(chatId) {
  const codes = await listDiscounts();
  let text = '🎟 **کدهای تخفیف**\n';
  const kb = codes.map((d) => [{
    text: `${d.isActive ? '✅' : '⛔'} ${d.code} | ${d.percent}% | ${d.usedCount}/${d.maxUses || '∞'}`,
    callback_data: `discount_detail:${d.id}`,
  }]);
  kb.push([{ text: '➕ افزودن کد تخفیف', callback_data: 'discount_add' }]);
  await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kb }, parse_mode: 'Markdown' });
}

export async function discountsMenu(message) {
  if (!(await isAdmin(message.from.id))) return;
  await renderDiscountsList(message.chat.id);
}

export async function discountDetailCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  const d = await getDiscountById(id);
  if (!d) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  const text = `🎟 **${d.code}**\n📉 درصد: ${d.percent}%\n🔢 استفاده: ${d.usedCount}/${d.maxUses || '∞'}\n💰 حداقل مبلغ: ${d.minAmount}\n🎯 فقط اولین خرید: ${d.isFirstPurchase ? 'بله' : 'خیر'}\n🔄 فقط تمدید: ${d.isRenewal ? 'بله' : 'خیر'}\n🚦 ${d.isActive ? 'فعال' : 'غیرفعال'}`;
  const kb = {
    inline_keyboard: [
      [{ text: d.isActive ? '⛔ غیرفعال کردن' : '✅ فعال کردن', callback_data: `discount_toggle:${id}` }],
      [{ text: '🗑 حذف', callback_data: `discount_delete:${id}` }],
    ],
  };
  await api.sendMessage({ chat_id: callback.message.chat.id, text, reply_markup: kb, parse_mode: 'Markdown' });
}

export async function discountToggleCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  const d = await getDiscountById(id);
  if (!d) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await updateDiscount(id, { isActive: !d.isActive });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '✅ به‌روزرسانی شد' });
}

export async function discountDeleteCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  await deleteDiscount(id);
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '🗑 حذف شد' });
  await renderDiscountsList(callback.message.chat.id);
}

export async function discountAddCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  await setState(callback.from.id, 'admin:discount_add', {});
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await api.sendMessage({
    chat_id: callback.message.chat.id,
    text: '➕ اطلاعات کد تخفیف را در ۶ خط ارسال کنید:\n`کد`\n`درصد تخفیف`\n`حداقل مبلغ خرید (صفر = بدون محدودیت)`\n`حداکثر تعداد استفاده (صفر = نامحدود)`\n`فقط اولین خرید؟ بله/خیر`\n`فقط تمدید؟ بله/خیر`\n\nمثال:\n`WELCOME20`\n`20`\n`0`\n`100`\n`بله`\n`خیر`',
    parse_mode: 'Markdown', reply_markup: CANCEL_MENU,
  });
}

export async function processDiscountAdd(message) {
  if (message.text === '❌ انصراف') {
    await clearState(message.from.id);
    return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU });
  }
  const lines = (message.text || '').trim().split('\n').map((l) => l.trim()).filter(Boolean);
  if (lines.length < 6) return api.sendMessage({ chat_id: message.chat.id, text: '❌ باید دقیقاً ۶ خط ارسال کنید.' });
  const [codeRaw, percentStr, minAmountStr, maxUsesStr, firstPurchaseStr, renewalStr] = lines;
  const code = codeRaw.toUpperCase();
  const percent = parseInt(percentStr, 10);
  if (Number.isNaN(percent) || percent <= 0 || percent > 100) return api.sendMessage({ chat_id: message.chat.id, text: '❌ درصد نامعتبر است (۱ تا ۱۰۰).' });
  const minAmount = parseInt(minAmountStr, 10) || 0;
  const maxUses = parseInt(maxUsesStr, 10) || 0;
  const isFirstPurchase = /^(بله|yes|y|true)$/i.test(firstPurchaseStr.trim());
  const isRenewal = /^(بله|yes|y|true)$/i.test(renewalStr.trim());
  try {
    await createDiscount({ code, percent, minAmount, maxUses, isFirstPurchase, isRenewal, isActive: true, usedCount: 0 });
  } catch (e) {
    return api.sendMessage({ chat_id: message.chat.id, text: `❌ این کد قبلاً وجود دارد یا خطا رخ داد: ${e.message || e}` });
  }
  await clearState(message.from.id);
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ کد تخفیف \`${code}\` اضافه شد.`, parse_mode: 'Markdown', reply_markup: ADMIN_MENU });
}
