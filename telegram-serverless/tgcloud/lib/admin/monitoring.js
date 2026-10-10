// Port of bot/handlers/monitoring.py — quick live dashboard.
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import { countUsers } from '../db/users.js';
import { countAll, countActive, countInactive } from '../db/configs.js';
import { countPending } from '../db/payments.js';
import { listServers } from '../db/servers.js';
import { getServerStatus } from '../panel.js';
import { countOpenTickets } from '../db/tickets.js';

export async function showMonitoring(message) {
  if (!(await isAdmin(message.from.id))) return;
  const [userCount, totalConfigs, activeConfigs, inactiveConfigs, pendingPayments, openTickets, servers] = await Promise.all([
    countUsers(), countAll(), countActive(false), countInactive(), countPending(), countOpenTickets(), listServers(),
  ]);

  let text = '🖥 **مانیتورینگ سیستم**\n\n' +
    `👥 کاربران: \`${userCount}\`\n` +
    `📦 کل کانفیگ‌ها: \`${totalConfigs}\` (فعال: ${activeConfigs} | غیرفعال: ${inactiveConfigs})\n` +
    `💳 پرداخت‌های در انتظار: \`${pendingPayments}\`\n` +
    `🎫 تیکت‌های باز: \`${openTickets}\`\n\n` +
    '🖥 **وضعیت سرورها:**\n';

  for (const s of servers) {
    if (!s.isActive) { text += `⛔ ${s.name}: غیرفعال\n`; continue; }
    try {
      const status = await getServerStatus(s.id);
      text += status.success ? `✅ ${s.name}: آنلاین\n` : `⚠️ ${s.name}: ${status.msg}\n`;
    } catch (e) {
      text += `❌ ${s.name}: خطا (${e.message || e})\n`;
    }
  }
  if (!servers.length) text += '⚠️ هیچ سروری ثبت نشده است.\n';

  await api.sendMessage({ chat_id: message.chat.id, text, parse_mode: 'Markdown' });
}
