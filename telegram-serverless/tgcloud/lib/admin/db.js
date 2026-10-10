// Replaces bot/handlers/admin.py's file-copy DB backup/restore (`shutil.copy`
// of vpn_bot.db) — there is no filesystem or raw sqlite-file access on
// Telegram Serverless, so this exports/imports a JSON dump of every table
// instead (everything except the ephemeral `states` FSM table).
import { db, api, InputFile } from 'sdk';
import { isAdmin } from '../auth.js';
import { setState, clearState } from '../state.js';
import { ADMIN_MENU, CANCEL_MENU } from '../keyboards.js';
import {
  users, admins, payments, configs, settings, packages, tickets, ticketMessages, discountCodes, servers, contentLinks,
} from '../../schema.js';

const TABLES = [
  ['users', users], ['admins', admins], ['payments', payments], ['configs', configs],
  ['settings', settings], ['packages', packages], ['tickets', tickets], ['ticketMessages', ticketMessages],
  ['discountCodes', discountCodes], ['servers', servers], ['contentLinks', contentLinks],
];

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;

function dateReviver(_key, value) {
  return typeof value === 'string' && ISO_DATE_RE.test(value) ? new Date(value) : value;
}

export async function dbMenu(message) {
  if (!(await isAdmin(message.from.id))) return;
  const kb = { inline_keyboard: [
    [{ text: '📤 خروجی JSON', callback_data: 'db_export' }],
    [{ text: '📥 بازیابی از JSON', callback_data: 'db_import' }],
  ] };
  await api.sendMessage({ chat_id: message.chat.id, text: '🗳 **مدیریت دیتابیس**\n⚠️ بازیابی، تمام اطلاعات فعلی را با فایل جدید جایگزین می‌کند.', reply_markup: kb, parse_mode: 'Markdown' });
}

export async function dbExportCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '⏳ در حال تهیه خروجی...' });
  const dump = {};
  let total = 0;
  for (const [name, table] of TABLES) {
    const rows = await db.select().from(table).all();
    dump[name] = rows;
    total += rows.length;
  }
  const json = JSON.stringify(dump, null, 2);
  const bytes = new TextEncoder().encode(json);
  const filename = `vpnbot_backup_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.json`;
  try {
    await api.sendDocument({
      chat_id: callback.message.chat.id,
      document: new InputFile(bytes, filename, { type: 'application/json' }),
      caption: `🗳 نسخه پشتیبان دیتابیس — ${total} رکورد در ${TABLES.length} جدول.`,
    });
  } catch (e) {
    await api.sendMessage({ chat_id: callback.message.chat.id, text: `❌ ارسال فایل پشتیبان ناموفق بود: ${e.message || e}` });
  }
}

export async function dbImportCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  await setState(callback.from.id, 'admin:db_import', {});
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  await api.sendMessage({
    chat_id: callback.message.chat.id,
    text: '📥 فایل JSON پشتیبان (ساخته‌شده توسط همین ربات) را ارسال کنید.\n⚠️ تمام اطلاعات فعلی (کاربران، پرداخت‌ها، کانفیگ‌ها، تنظیمات، ...) با محتوای فایل جایگزین خواهد شد!',
    reply_markup: CANCEL_MENU,
  });
}

export async function processDbImport(message) {
  if (message.text === '❌ انصراف') {
    await clearState(message.from.id);
    return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU });
  }
  if (!message.document) return api.sendMessage({ chat_id: message.chat.id, text: '❌ لطفاً یک فایل JSON ارسال کنید (یا /cancel).' });
  await clearState(message.from.id);
  await api.sendMessage({ chat_id: message.chat.id, text: '⏳ در حال بازیابی...' });
  try {
    const bytes = await api.getFileContent(message.document.file_id);
    const text = new TextDecoder().decode(bytes);
    const dump = JSON.parse(text, dateReviver);
    let total = 0;
    for (const [name, table] of TABLES) {
      const rows = Array.isArray(dump[name]) ? dump[name] : [];
      await db.delete(table).run();
      if (rows.length) {
        await db.insert(table).values(rows).run();
        total += rows.length;
      }
    }
    await api.sendMessage({ chat_id: message.chat.id, text: `✅ بازیابی با موفقیت انجام شد (${total} رکورد).`, reply_markup: ADMIN_MENU });
  } catch (e) {
    console.error('db import failed', e);
    await api.sendMessage({ chat_id: message.chat.id, text: `❌ بازیابی ناموفق بود: ${e.message || e}`, reply_markup: ADMIN_MENU });
  }
}
