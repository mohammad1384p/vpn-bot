// Port of the admin CRUD half of bot/handlers/content_links.py.
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import {
  listContentLinks, getContentLinkById, createContentLink, updateContentLink, deleteContentLink,
} from '../db/contentLinks.js';
import { getSetting } from '../db/settings.js';
import { setState, getState, clearState } from '../state.js';
import { ADMIN_MENU, CANCEL_MENU } from '../keyboards.js';
import { randomHex } from '../helpers.js';

function detectContent(message) {
  if (message.photo) return { contentType: 'photo', contentFileId: message.photo[message.photo.length - 1].file_id, contentCaption: message.caption || null };
  if (message.document) return { contentType: 'document', contentFileId: message.document.file_id, contentCaption: message.caption || null };
  if (message.video) return { contentType: 'video', contentFileId: message.video.file_id, contentCaption: message.caption || null };
  if (message.audio) return { contentType: 'audio', contentFileId: message.audio.file_id, contentCaption: message.caption || null };
  if (message.voice) return { contentType: 'voice', contentFileId: message.voice.file_id, contentCaption: message.caption || null };
  if (message.text) return { contentType: 'text', contentText: message.text };
  return null;
}

async function renderContentLinksList(chatId) {
  const links = await listContentLinks();
  let text = '📢 **لینک‌های محتوا**\n';
  const kb = links.map((l) => [{ text: `${l.isActive ? '✅' : '⛔'} ${l.title || l.code} | 👁 ${l.views}`, callback_data: `cl_detail:${l.id}` }]);
  kb.push([{ text: '➕ افزودن لینک', callback_data: 'cl_add' }]);
  await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kb }, parse_mode: 'Markdown' });
}

export async function contentLinksMenu(message) {
  if (!(await isAdmin(message.from.id))) return;
  await renderContentLinksList(message.chat.id);
}

export async function clDetailCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  const l = await getContentLinkById(id);
  if (!l) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  const botUsername = await getSetting('bot_username', '');
  const link = botUsername ? `https://t.me/${botUsername}?start=content_${l.code}` : `(start=content_${l.code})`;
  const text = `📢 **${l.title || l.code}**\n🔗 \`${link}\`\n👁 بازدید: ${l.views}\n📣 تبلیغ: ${l.hasAd ? 'دارد' : 'ندارد'}\n🚦 ${l.isActive ? 'فعال' : 'غیرفعال'}`;
  const kb = {
    inline_keyboard: [
      [{ text: l.isActive ? '⛔ غیرفعال کردن' : '✅ فعال کردن', callback_data: `cl_toggle:${id}` }],
      [{ text: '🗑 حذف', callback_data: `cl_delete:${id}` }],
    ],
  };
  await api.sendMessage({ chat_id: callback.message.chat.id, text, reply_markup: kb, parse_mode: 'Markdown' });
}

export async function clToggleCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  const l = await getContentLinkById(id);
  if (!l) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'یافت نشد', show_alert: true });
  await updateContentLink(id, { isActive: !l.isActive });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '✅ به‌روزرسانی شد' });
}

export async function clDeleteCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const id = parseInt(callback.data.split(':')[1], 10);
  await deleteContentLink(id);
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '🗑 حذف شد' });
  await renderContentLinksList(callback.message.chat.id);
}

export async function clAddCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  await setState(callback.from.id, 'admin:cl_waiting_content', {});
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await api.sendMessage({
    chat_id: callback.message.chat.id,
    text: '➕ محتوایی که می‌خواهید پشت لینک قرار بگیرد را ارسال کنید (متن، عکس، ویدیو، فایل یا صدا):',
    reply_markup: CANCEL_MENU,
  });
}

function cancelable(message) { return message.text === '❌ انصراف'; }

export async function processClContent(message) {
  if (cancelable(message)) { await clearState(message.from.id); return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU }); }
  const content = detectContent(message);
  if (!content) return api.sendMessage({ chat_id: message.chat.id, text: '❌ نوع پیام پشتیبانی نمی‌شود. دوباره ارسال کنید.' });
  await setState(message.from.id, 'admin:cl_waiting_meta', { content });
  await api.sendMessage({
    chat_id: message.chat.id,
    text: '📝 یک عنوان کوتاه برای این لینک ارسال کنید (برای کد تصادفی به جای عنوان از `-` استفاده کنید):',
    parse_mode: 'Markdown',
  });
}

export async function processClMeta(message) {
  if (cancelable(message)) { await clearState(message.from.id); return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU }); }
  const state = await getState(message.from.id);
  const title = (message.text || '').trim();
  await setState(message.from.id, 'admin:cl_waiting_ad', { ...state.data, title: title === '-' ? null : title });
  await api.sendMessage({
    chat_id: message.chat.id,
    text: '📣 اگر می‌خواهید قبل از نمایش محتوا یک تبلیغ نشان داده شود، متن یا عکس آن را ارسال کنید.\nبرای رد کردن این مرحله `-` را ارسال کنید.',
  });
}

export async function processClAd(message) {
  if (cancelable(message)) { await clearState(message.from.id); return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU }); }
  const state = await getState(message.from.id);
  const { content, title } = state.data;
  let hasAd = false;
  let adText = null;
  let adPhotoId = null;
  if (message.text !== '-') {
    hasAd = true;
    if (message.photo) { adPhotoId = message.photo[message.photo.length - 1].file_id; adText = message.caption || null; }
    else adText = message.text || null;
  }
  const code = randomHex(5);
  await createContentLink({
    code, title, createdBy: message.from.id, hasAd, adText, adPhotoId, isActive: true, views: 0, ...content,
  });
  await clearState(message.from.id);
  const botUsername = await getSetting('bot_username', '');
  const link = botUsername ? `https://t.me/${botUsername}?start=content_${code}` : `(ربات یوزرنیم ندارد — در تنظیمات اولیه وارد کنید؛ کد: content_${code})`;
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ لینک ساخته شد:\n\`${link}\``, parse_mode: 'Markdown', reply_markup: ADMIN_MENU });
}
