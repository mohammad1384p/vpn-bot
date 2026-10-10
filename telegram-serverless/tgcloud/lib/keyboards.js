// Reply/inline keyboards as plain Bot API objects (aiogram's
// ReplyKeyboardMarkup/InlineKeyboardMarkup are just sugar over this shape).

export const MAIN_MENU = {
  keyboard: [
    [{ text: '🛒 خرید کانفیگ' }, { text: '🔄 تمدید' }],
    [{ text: '📦 سرویس‌های من' }, { text: '🎁 اکانت تست' }],
    [{ text: '👥 کیف پول' }, { text: '👥 زیرمجموعه‌گیری' }],
    [{ text: '🎓 راهنما' }, { text: '🎫 پشتیبانی' }],
    [{ text: '🏆 رتبه من' }, { text: '🎟 کد تخفیف' }],
  ],
  resize_keyboard: true,
  is_persistent: true,
};

export const PHONE_KB = {
  keyboard: [[{ text: '📱 ارسال شماره تماس', request_contact: true }]],
  resize_keyboard: true,
};

export const HELP_MENU = {
  keyboard: [
    [{ text: '🤖 اندروید' }, { text: '🍎 آیفون' }],
    [{ text: '💻 ویندوز' }, { text: '🔙 بازگشت به منو' }],
  ],
  resize_keyboard: true,
};

export const TICKET_MENU = {
  keyboard: [
    [{ text: '🎫 تیکت جدید' }],
    [{ text: '📋 تیکت‌های من' }],
    [{ text: '🔙 بازگشت به منو' }],
  ],
  resize_keyboard: true,
};

export const CANCEL_MENU = {
  keyboard: [[{ text: '❌ انصراف' }]],
  resize_keyboard: true,
};

export const BACK_MENU = {
  keyboard: [[{ text: '🔙 بازگشت به منو' }]],
  resize_keyboard: true,
};

export const DISCOUNT_INFO_MENU = {
  keyboard: [[{ text: '🛒 خرید کانفیگ' }], [{ text: '🔄 تمدید' }], [{ text: '🔙 بازگشت به منو' }]],
  resize_keyboard: true,
};

export const ADMIN_MENU = {
  keyboard: [
    [{ text: '⚙️ تنظیمات اولیه' }, { text: '🖥 مانیتورینگ' }],
    [{ text: '💰 مالی' }, { text: '📦 بسته‌ها' }],
    [{ text: '🎟 تخفیف‌ها' }, { text: '🎫 تیکت‌ها' }],
    [{ text: '📢 لینک‌های محتوا' }, { text: '📊 گزارش‌ها' }],
    [{ text: '👥 کاربران' }, { text: '👮 ادمین‌ها' }],
    [{ text: '📢 همگانی' }, { text: '🗳 دیتابیس' }],
  ],
  resize_keyboard: true,
};

export function inline(rows) {
  return { inline_keyboard: rows };
}

export function removeKeyboard() {
  return { remove_keyboard: true };
}
