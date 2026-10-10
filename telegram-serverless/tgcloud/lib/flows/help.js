// Port of bot/handlers/help.py
import { api } from 'sdk';
import { HELP_MENU } from '../keyboards.js';
import { getSetting } from '../db/settings.js';

export async function showHelpMenu(message) {
  await api.sendMessage({ chat_id: message.chat.id, text: '🎓 **راهنمای اتصال:**', reply_markup: HELP_MENU, parse_mode: 'Markdown' });
}

const OS_MAP = { '🤖 اندروید': 'help_android', '🍎 آیفون': 'help_ios', '💻 ویندوز': 'help_windows' };

export async function showOsHelp(message) {
  const key = OS_MAP[message.text];
  const link = await getSetting(key, '');
  if (!link) {
    await api.sendMessage({ chat_id: message.chat.id, text: '⚠️ آموزش برای این سیستم عامل هنوز تنظیم نشده است.' });
    return;
  }
  await api.sendMessage({
    chat_id: message.chat.id,
    text: `📱 **آموزش اتصال (${message.text}):**\n🔗 [کلیک کنید و آموزش را مشاهده نمایید](${link})\n📋 یا لینک زیر را کپی کنید:\n\`${link}\``,
    parse_mode: 'Markdown',
  });
}

export function isOsHelpButton(text) {
  return Object.prototype.hasOwnProperty.call(OS_MAP, text);
}
