// Port of bot/utils/helpers.py::send_config_package. Sends the QR code +
// sub-link + tutorial buttons to the user and notifies all admins.
import { api, BotApiError } from 'sdk';
import { getSetting } from './db/settings.js';
import { getAllAdminIds } from './auth.js';
import { qrCodeUrl } from './config.js';

export async function sendConfigPackage({
  userId, subLink, username, volumeDisplay, durationDisplay, isRenew = false, isTest = false,
}) {
  const helpAndroid = await getSetting('help_android', '');
  const helpIos = await getSetting('help_ios', '');
  const helpWindows = await getSetting('help_windows', '');
  const supportUsername = await getSetting('support_username', '');

  let actionText;
  if (isTest) actionText = '🎁 <b>اکانت تست شما آماده شد!</b>';
  else if (isRenew) actionText = '🔄 <b>تمدید با موفقیت انجام شد!</b>';
  else actionText = '✅ <b>خرید شما با موفقیت ثبت و فعال شد!</b>';

  let text = `${actionText}\n\n` +
    `👤 <b>نام کاربری:</b> <code>${username}</code>\n` +
    `📦 <b>حجم:</b> ${volumeDisplay}\n` +
    `⏱ <b>مدت زمان:</b> ${durationDisplay}\n\n` +
    `🔗 <b>لینک اشتراک (کلیک برای کپی):</b>\n` +
    `<code>${subLink}</code>\n\n`;

  if (!(helpAndroid || helpIos || helpWindows)) {
    text += '⚠️ <i>لینک آموزشی تنظیم نشده است.</i>\n';
  }
  text += `\n🎫 <b>پشتیبانی:</b> @${supportUsername || 'Support'}\n`;
  text += '💡 <i>برای استفاده، لینک اشتراک را در برنامه خود وارد کنید یا از QR Code زیر استفاده نمایید.</i>';

  const helpRow = [];
  if (helpAndroid) helpRow.push({ text: '🤖 آموزش اندروید', url: helpAndroid });
  if (helpIos) helpRow.push({ text: '🍎 آموزش آیفون', url: helpIos });
  if (helpWindows) helpRow.push({ text: '💻 آموزش ویندوز', url: helpWindows });
  const kbRows = [];
  if (helpRow.length) kbRows.push(helpRow);
  kbRows.push([{ text: '📦 سرویس‌های من', callback_data: 'back_to_services' }]);
  kbRows.push([{ text: '🏠 منوی اصلی', callback_data: 'back_to_main_menu' }]);
  const kb = { inline_keyboard: kbRows };

  try {
    await api.sendPhoto({
      chat_id: userId, photo: qrCodeUrl(subLink), caption: text, parse_mode: 'HTML', reply_markup: kb,
    });
  } catch (e) {
    console.error('send_config_package photo failed', e);
    try {
      await api.sendMessage({ chat_id: userId, text, parse_mode: 'HTML', reply_markup: kb });
    } catch (e2) {
      console.error('send_config_package message failed', e2);
      const plain = `${isTest ? '🎁 اکانت تست' : (isRenew ? '🔄 تمدید' : '✅ خرید')} آماده شد!\n` +
        `نام کاربری: ${username}\nحجم: ${volumeDisplay}\nمدت: ${durationDisplay}\nلینک:\n${subLink}`;
      await api.sendMessage({ chat_id: userId, text: plain, reply_markup: kb });
    }
  }

  const adminIds = await getAllAdminIds();
  const typeText = isTest ? '🧪 اکانت تست' : (isRenew ? '🔄 تمدید' : '🛒 خرید جدید');
  const notifyText = '✅ **کانفیگ با موفقیت برای کاربر ارسال شد!**\n\n' +
    `👤 **آیدی کاربر:** \`${userId}\`\n` +
    `🆔 **نام کاربری:** \`${username}\`\n` +
    `📦 **حجم:** ${volumeDisplay}\n` +
    `⏱ **مدت زمان:** ${durationDisplay}\n` +
    `🎯 **نوع عملیات:** ${typeText}`;
  for (const adminId of adminIds) {
    try {
      await api.sendMessage({ chat_id: adminId, text: notifyText, parse_mode: 'Markdown' });
    } catch (e) {
      if (!(e instanceof BotApiError)) throw e;
    }
  }
}
