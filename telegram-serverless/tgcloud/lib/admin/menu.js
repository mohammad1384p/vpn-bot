import { api } from 'sdk';
import { isAdmin, getAdminInfo } from '../auth.js';
import { ADMIN_MENU } from '../keyboards.js';

export async function showAdminMenu(message) {
  if (!(await isAdmin(message.from.id))) {
    return api.sendMessage({ chat_id: message.chat.id, text: '⛔ شما دسترسی ادمین ندارید.' });
  }
  const info = await getAdminInfo(message.from.id);
  await api.sendMessage({
    chat_id: message.chat.id,
    text: `👮 **پنل مدیریت**\nنقش: ${info?.isSuper ? '👑 سوپرادمین' : info?.role || 'admin'}`,
    reply_markup: ADMIN_MENU, parse_mode: 'Markdown',
  });
}
