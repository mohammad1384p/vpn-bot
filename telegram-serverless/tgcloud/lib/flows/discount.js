// Port of bot/handlers/discount.py — user-facing "how discount codes work" help
// screen (the actual code entry happens inline in the payment/renew flows).
import { api } from 'sdk';
import { DISCOUNT_INFO_MENU, BACK_MENU } from '../keyboards.js';

const INFO_TEXT = 'ℹ️ **کدهای تخفیف**\n\n' +
  '🎟 کد تخفیف یک کد حرفی/عددی است که هنگام خرید یا تمدید سرویس می‌توانید وارد کنید تا درصدی از مبلغ خرید شما کسر شود.\n\n' +
  '• برخی کدها فقط برای **اولین خرید** معتبرند.\n' +
  '• برخی کدها فقط برای **تمدید** سرویس معتبرند.\n' +
  '• هر کد ممکن است **حداقل مبلغ خرید** و **سقف تعداد استفاده** داشته باشد.\n' +
  '• کد تخفیف را هنگام خرید/تمدید، در مرحله‌ای که از شما خواسته می‌شود، ارسال کنید.\n\n' +
  '📩 برای دریافت کد تخفیف فعال، با پشتیبانی در ارتباط باشید یا منتظر کمپین‌های بعدی بمانید.';

export async function showDiscountInfo(message) {
  await api.sendMessage({ chat_id: message.chat.id, text: INFO_TEXT, parse_mode: 'Markdown', reply_markup: DISCOUNT_INFO_MENU });
}

export async function backFromDiscountInfo(message) {
  const { showMainMenu } = await import('./start.js');
  await showMainMenu(message.chat.id, message.from.id, message.from.first_name);
}
