// Forced-join channel check. Mirrors check_user_membership in bot/handlers/start.py.
import { api, BotApiError } from 'sdk';
import { getChannelIds } from './db/settings.js';

export async function checkUserMembership(userId) {
  const channelIds = await getChannelIds();
  if (!channelIds.length) return [];
  const notJoined = [];
  for (const chatId of channelIds) {
    try {
      const member = await api.getChatMember({ chat_id: chatId, user_id: userId });
      if (member.status === 'left' || member.status === 'kicked') {
        let username = String(chatId).replace('-100', '');
        let title = 'کانال';
        try {
          const chatInfo = await api.getChat({ chat_id: chatId });
          if (chatInfo.username) username = chatInfo.username;
          title = chatInfo.title || title;
        } catch { /* keep fallback */ }
        notJoined.push({ id: chatId, username, title });
      }
    } catch (e) {
      // getChatMember can fail (bot not in chat, user never started it, etc.) —
      // same silent swallow as the Python `except Exception: pass`.
      if (!(e instanceof BotApiError)) throw e;
    }
  }
  return notJoined;
}

export function joinKeyboard(notJoined, checkCallbackData) {
  const rows = notJoined.map((ch) => ([{ text: `📢 عضویت در ${ch.title}`, url: `https://t.me/${ch.username}` }]));
  rows.push([{ text: '✅ بررسی عضویت', callback_data: checkCallbackData }]);
  return { inline_keyboard: rows };
}
