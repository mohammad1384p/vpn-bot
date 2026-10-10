// Port of bot/handlers/content_links.py — shareable "content" deep-links,
// gated behind the bot's forced-join channels and an optional ad screen.
import { api } from 'sdk';
import { checkUserMembership, joinKeyboard } from '../membership.js';
import { getContentLinkByCode, incrementViews } from '../db/contentLinks.js';

export const CONTENT_START_PREFIX = 'content_';

export async function startContentLink(message, rawCode) {
  const code = rawCode.slice(CONTENT_START_PREFIX.length);
  const link = await getContentLinkByCode(code);
  if (!link || !link.isActive) {
    await api.sendMessage({ chat_id: message.chat.id, text: '❌ این لینک معتبر نیست یا حذف شده است.' });
    return;
  }
  const notJoined = await checkUserMembership(message.from.id);
  if (notJoined.length) {
    await api.sendMessage({
      chat_id: message.chat.id,
      text: '👋 برای مشاهده این محتوا، ابتدا در کانال‌های زیر عضو شوید:',
      reply_markup: joinKeyboard(notJoined, `check_join_content:${code}`),
    });
    return;
  }
  await deliverOrGateContent(message.chat.id, link);
}

export async function checkJoinContentCallback(callback) {
  const code = callback.data.split(':')[1];
  const link = await getContentLinkByCode(code);
  if (!link) {
    await api.answerCallbackQuery({ callback_query_id: callback.id, text: 'لینک یافت نشد', show_alert: true });
    return;
  }
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '⏳ در حال بررسی...' });
  const notJoined = await checkUserMembership(callback.from.id);
  if (notJoined.length) {
    await api.editMessageText({
      chat_id: callback.message.chat.id, message_id: callback.message.message_id,
      text: '⚠️ هنوز در تمام کانال‌ها عضو نشده‌اید:',
      reply_markup: joinKeyboard(notJoined, `check_join_content:${code}`),
    });
    return;
  }
  await api.editMessageText({ chat_id: callback.message.chat.id, message_id: callback.message.message_id, text: '✅ عضویت تأیید شد!' });
  await deliverOrGateContent(callback.message.chat.id, link);
}

export async function revealContentCallback(callback) {
  const code = callback.data.split(':')[1];
  const link = await getContentLinkByCode(code);
  if (!link || !link.isActive) {
    await api.answerCallbackQuery({ callback_query_id: callback.id, text: 'این لینک دیگر در دسترس نیست', show_alert: true });
    return;
  }
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await deliverContent(callback.message.chat.id, link);
}

async function deliverOrGateContent(chatId, link) {
  if (link.hasAd) {
    const kb = { inline_keyboard: [[{ text: '➡️ مشاهده محتوا', callback_data: `reveal_content:${link.code}` }]] };
    try {
      if (link.adPhotoId) {
        await api.sendPhoto({ chat_id: chatId, photo: link.adPhotoId, caption: link.adText || '📢 تبلیغ', reply_markup: kb });
      } else {
        await api.sendMessage({ chat_id: chatId, text: link.adText || '📢 تبلیغ', reply_markup: kb });
      }
    } catch (e) {
      console.error('content link ad send failed', e);
      await deliverContent(chatId, link);
    }
    return;
  }
  await deliverContent(chatId, link);
}

async function deliverContent(chatId, link) {
  await incrementViews(link.id);
  const caption = link.contentCaption || link.title || undefined;
  try {
    switch (link.contentType) {
      case 'photo':
        await api.sendPhoto({ chat_id: chatId, photo: link.contentFileId, caption });
        break;
      case 'document':
        await api.sendDocument({ chat_id: chatId, document: link.contentFileId, caption });
        break;
      case 'video':
        await api.sendVideo({ chat_id: chatId, video: link.contentFileId, caption });
        break;
      case 'audio':
        await api.sendAudio({ chat_id: chatId, audio: link.contentFileId, caption });
        break;
      case 'voice':
        await api.sendVoice({ chat_id: chatId, voice: link.contentFileId, caption });
        break;
      default:
        await api.sendMessage({ chat_id: chatId, text: link.contentText || link.title || '(بدون محتوا)' });
    }
  } catch (e) {
    console.error('content link delivery failed', e);
    await api.sendMessage({ chat_id: chatId, text: '❌ ارسال محتوا با خطا مواجه شد.' });
  }
}
