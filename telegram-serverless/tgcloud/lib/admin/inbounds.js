// Port of bot/handlers/inbounds.py — pick which panel inbound ids new clients
// get attached to (stored as a comma-separated settings.selected_inbound_ids).
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import { listServers } from '../db/servers.js';
import { getInboundOptions } from '../panel.js';
import { getSetting, setSetting, getSelectedInboundIds } from '../db/settings.js';

export async function inboundsMenu(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  await api.answerCallbackQuery({ callback_query_id: callback.id });
  const servers = await listServers();
  if (!servers.length) {
    return api.sendMessage({ chat_id: callback.message.chat.id, text: '⚠️ ابتدا یک سرور اضافه کنید.' });
  }
  const rows = servers.map((s) => [{ text: `🖥 ${s.name}`, callback_data: `inbound_server:${s.id}` }]);
  await api.sendMessage({ chat_id: callback.message.chat.id, text: '🔌 سرور را برای انتخاب اینباند فعال انتخاب کنید:', reply_markup: { inline_keyboard: rows } });
}

export async function inboundServerCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const serverId = parseInt(callback.data.split(':')[1], 10);
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '⏳ در حال دریافت لیست...' });
  const res = await getInboundOptions(serverId);
  if (!res.success) {
    return api.sendMessage({ chat_id: callback.message.chat.id, text: `❌ ${res.msg}` });
  }
  const selected = new Set(await getSelectedInboundIds());
  const rows = res.inbounds.map((ib) => {
    const checked = selected.has(ib.id) ? '✅ ' : '';
    return [{ text: `${checked}${ib.remark || ib.tag || ''} (#${ib.id})`, callback_data: `inbound_toggle:${serverId}:${ib.id}` }];
  });
  rows.push([{ text: '✅ ذخیره و پایان', callback_data: 'inbound_done' }]);
  await api.sendMessage({ chat_id: callback.message.chat.id, text: '🔌 اینباندهای فعال را انتخاب کنید (برای تغییر وضعیت لمس کنید):', reply_markup: { inline_keyboard: rows } });
}

export async function inboundToggleCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const [, , ibIdStr] = callback.data.split(':');
  const ibId = parseInt(ibIdStr, 10);
  const selected = new Set(await getSelectedInboundIds());
  if (selected.has(ibId)) selected.delete(ibId); else selected.add(ibId);
  await setSetting('selected_inbound_ids', [...selected].join(','));
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: selected.has(ibId) ? '✅ انتخاب شد' : '❌ حذف شد' });
}

export async function inboundDoneCallback(callback) {
  if (!(await isAdmin(callback.from.id))) return;
  const ids = await getSelectedInboundIds();
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '✅ ذخیره شد' });
  await api.sendMessage({ chat_id: callback.message.chat.id, text: `✅ اینباندهای انتخابی: \`${ids.join(', ') || '-'}\``, parse_mode: 'Markdown' });
}
