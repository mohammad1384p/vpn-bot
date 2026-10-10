// Port of bot/handlers/report.py — aggregate financial/usage reports.
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import { countUsers } from '../db/users.js';
import { countAll, countActive, countInactive, sampleActive } from '../db/configs.js';
import { sumApprovedTotal, sumApprovedOnDate, countPending } from '../db/payments.js';
import { formatNumber } from '../helpers.js';

function todayUtcStr(offsetDays = 0) {
  const d = new Date(Date.now() + offsetDays * 86400000);
  return d.toISOString().slice(0, 10);
}

export async function showReport(message) {
  if (!(await isAdmin(message.from.id))) return;
  const [userCount, totalConfigs, activeConfigs, inactiveConfigs, pendingPayments, totalRevenue] = await Promise.all([
    countUsers(), countAll(), countActive(false), countInactive(), countPending(), sumApprovedTotal(),
  ]);
  const today = await sumApprovedOnDate(todayUtcStr());
  const yesterday = await sumApprovedOnDate(todayUtcStr(-1));
  const sampleTest = await sampleActive(true, 5);
  const sampleReal = await sampleActive(false, 5);

  const text = '📊 **گزارش کلی**\n\n' +
    `👥 کاربران: \`${userCount}\`\n` +
    `📦 کانفیگ‌ها: \`${totalConfigs}\` (فعال: ${activeConfigs} | غیرفعال: ${inactiveConfigs})\n` +
    `💳 پرداخت‌های در انتظار: \`${pendingPayments}\`\n\n` +
    `💰 **درآمد (تومان):**\n` +
    `📅 امروز: \`${formatNumber(today.sum)}\` (${today.count} تراکنش)\n` +
    `📅 دیروز: \`${formatNumber(yesterday.sum)}\` (${yesterday.count} تراکنش)\n` +
    `💵 کل: \`${formatNumber(totalRevenue)}\`\n\n` +
    `🧪 نمونه کانفیگ تست فعال: ${sampleTest.length}\n` +
    `🔗 نمونه کانفیگ فعال: ${sampleReal.length}`;
  await api.sendMessage({ chat_id: message.chat.id, text, parse_mode: 'Markdown' });
}
