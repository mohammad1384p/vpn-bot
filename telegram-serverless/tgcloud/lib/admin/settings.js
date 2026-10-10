// Port of bot/handlers/config_settings.py — simplified into a single
// "pick a field, then send its new value" wizard (the polling bot chains a
// long sequence of aiogram FSM prompts; that is collapsed here to keep the
// state machine small, but every underlying setting is still editable).
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import { getSetting, setSetting } from '../db/settings.js';
import { setState, getState, clearState } from '../state.js';
import { ADMIN_MENU, CANCEL_MENU } from '../keyboards.js';

export const FIELDS = [
  { key: 'card_number', label: '💳 شماره کارت' },
  { key: 'card_name', label: '👤 نام صاحب کارت' },
  { key: 'support_username', label: '🎫 یوزرنیم پشتیبانی (بدون @)' },
  { key: 'bot_username', label: '🤖 یوزرنیم ربات (بدون @)' },
  { key: 'referral_reward', label: '👥 پاداش زیرمجموعه‌گیری (تومان)' },
  { key: 'channel_ids', label: '📢 آیدی عددی کانال‌های جوین اجباری (با کاما جدا کنید)' },
  { key: 'free_config_threshold', label: '🎁 حداقل مجموع خرید برای کانفیگ رایگان (تومان)' },
  { key: 'free_config_volume_gb', label: '🎁 حجم کانفیگ رایگان (GB)' },
  { key: 'free_config_duration_days', label: '🎁 مدت کانفیگ رایگان (روز)' },
  { key: 'test_cooldown_hours', label: '🧪 فاصله مجاز بین دو درخواست تست (ساعت)' },
  { key: 'test_volume_mb', label: '🧪 حجم اکانت تست (MB)' },
  { key: 'test_duration_hours', label: '🧪 مدت اکانت تست (ساعت)' },
  { key: 'max_test_per_user', label: '🧪 حداکثر تعداد اکانت تست فعال هر کاربر' },
  { key: 'help_android', label: '🤖 لینک آموزش اندروید' },
  { key: 'help_ios', label: '🍎 لینک آموزش آیفون' },
  { key: 'help_windows', label: '💻 لینک آموزش ویندوز' },
  { key: 'sub_link_pattern', label: '🔗 الگوی سفارشی لینک اشتراک (خالی = پیش‌فرض پنل)' },
];

export async function settingsMenu(message) {
  if (!(await isAdmin(message.from.id))) return;
  const rows = FIELDS.map((f) => [{ text: f.label, callback_data: `setting_edit:${f.key}` }]);
  rows.push([{ text: '🖥 مدیریت سرورها', callback_data: 'servers_menu' }]);
  rows.push([{ text: '🔌 انتخاب اینباند فعال', callback_data: 'inbounds_menu' }]);
  await api.sendMessage({ chat_id: message.chat.id, text: '⚙️ **تنظیمات اولیه**\nیک مورد را برای ویرایش انتخاب کنید:', reply_markup: { inline_keyboard: rows }, parse_mode: 'Markdown' });
}

const FINANCIAL_KEYS = ['card_number', 'card_name', 'referral_reward', 'free_config_threshold'];

// The "💰 مالی" quick-access button on the admin menu — same underlying
// fields as settingsMenu() but filtered to the money-related ones.
export async function financialMenu(message) {
  if (!(await isAdmin(message.from.id))) return;
  const rows = FIELDS.filter((f) => FINANCIAL_KEYS.includes(f.key)).map((f) => [{ text: f.label, callback_data: `setting_edit:${f.key}` }]);
  await api.sendMessage({ chat_id: message.chat.id, text: '💰 **تنظیمات مالی**', reply_markup: { inline_keyboard: rows }, parse_mode: 'Markdown' });
}

export async function settingEditCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const key = callback.data.split(':')[1];
  const field = FIELDS.find((f) => f.key === key);
  if (!field) return api.answerCallbackQuery({ callback_query_id: callback.id, text: 'نامعتبر', show_alert: true });
  const current = await getSetting(key, '');
  await setState(callback.from.id, 'admin:setting_value', { key });
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await api.sendMessage({
    chat_id: callback.message.chat.id,
    text: `✏️ ${field.label}\nمقدار فعلی: \`${current || '-'}\`\n\nمقدار جدید را ارسال کنید (یا /cancel):`,
    parse_mode: 'Markdown', reply_markup: CANCEL_MENU,
  });
}

export async function processSettingValue(message) {
  if (message.text === '/cancel' || message.text === '❌ انصراف') {
    await clearState(message.from.id);
    return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU });
  }
  const state = await getState(message.from.id);
  const { key } = state.data;
  const value = (message.text || '').trim();
  await setSetting(key, value);
  await clearState(message.from.id);
  const field = FIELDS.find((f) => f.key === key);
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ ${field ? field.label : key} به‌روزرسانی شد.`, reply_markup: ADMIN_MENU });
}
