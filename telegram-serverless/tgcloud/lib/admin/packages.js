// Port of the package CRUD part of bot/handlers/packages.py / admin.py.
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import { listAllPackagesByIdDesc, getPackageById, createPackage, updatePackage, deletePackage } from '../db/packages.js';
import { setState, getState, clearState } from '../state.js';
import { ADMIN_MENU, CANCEL_MENU } from '../keyboards.js';
import { formatNumber } from '../helpers.js';

export async function packagesMenu(message) {
  if (!(await isAdmin(message.from.id))) return;
  await renderPackagesList(message.chat.id);
}

async function renderPackagesList(chatId) {
  const pkgs = await listAllPackagesByIdDesc();
  let text = '📦 **بسته‌ها**\n';
  const kb = pkgs.map((p) => [{
    text: `${p.isActive ? '✅' : '⛔'} ${p.name} | ${p.volumeGb || '♾️'}GB/${p.durationDays || '♾️'}d | ${formatNumber(p.price)}T`,
    callback_data: `pkg_detail:${p.id}`,
  }]);
  kb.push([{ text: '➕ افزودن بسته', callback_data: 'pkg_add' }]);
  await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kb }, parse_mode: 'Markdown' });
}

export async function pkgDetailCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  const p = await getPackageById(id);
  if (!p) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  const text = `📦 **${p.name}**\n📶 حجم: ${p.volumeGb || '♾️ نامحدود'}\n⏱ مدت: ${p.durationDays || '♾️ نامحدود'}\n💰 قیمت: \`${formatNumber(p.price)}\`\n🚦 ${p.isActive ? 'فعال' : 'غیرفعال'}`;
  const kb = {
    inline_keyboard: [
      [{ text: p.isActive ? '⛔ غیرفعال کردن' : '✅ فعال کردن', callback_data: `pkg_toggle:${id}` }],
      [{ text: '🗑 حذف', callback_data: `pkg_delete:${id}` }],
    ],
  };
  await api.sendMessage({ chat_id: callback.message.chat.id, text, reply_markup: kb, parse_mode: 'Markdown' });
}

export async function pkgToggleCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  const p = await getPackageById(id);
  if (!p) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await updatePackage(id, { isActive: !p.isActive });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '✅ به‌روزرسانی شد' });
}

export async function pkgDeleteCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  await deletePackage(id);
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '🗑 حذف شد' });
  await renderPackagesList(callback.message.chat.id);
}

export async function pkgAddCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  await setState(callback.from.id, 'admin:package_add', {});
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await api.sendMessage({
    chat_id: callback.message.chat.id,
    text: '➕ اطلاعات بسته جدید را در ۴ خط ارسال کنید:\n`نام`\n`حجم (GB، صفر = نامحدود)`\n`مدت (روز، صفر = نامحدود)`\n`قیمت (تومان)`\n\nمثال:\n`بسته ۲۰ گیگ`\n`20`\n`30`\n`150000`',
    parse_mode: 'Markdown', reply_markup: CANCEL_MENU,
  });
}

export async function processPackageAdd(message) {
  if (message.text === '❌ انصراف') {
    await clearState(message.from.id);
    return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU });
  }
  const lines = (message.text || '').trim().split('\n').map((l) => l.trim()).filter(Boolean);
  if (lines.length < 4) return api.sendMessage({ chat_id: message.chat.id, text: '❌ باید دقیقاً ۴ خط ارسال کنید.' });
  const [name, volStr, durStr, priceStr] = lines;
  const volumeGb = parseInt(volStr, 10) || 0;
  const durationDays = parseInt(durStr, 10) || 0;
  const price = parseInt(priceStr, 10);
  if (Number.isNaN(price)) return api.sendMessage({ chat_id: message.chat.id, text: '❌ قیمت نامعتبر است.' });
  await createPackage({ name, volumeGb, durationDays, price, isActive: true });
  await clearState(message.from.id);
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ بسته \`${name}\` اضافه شد.`, parse_mode: 'Markdown', reply_markup: ADMIN_MENU });
}
