// Port of bot/handlers/ranking.py — spending leaderboard + rank info.
import { api } from 'sdk';
import { getUserByTelegramId, topSpenders, countReferrals } from '../db/users.js';
import { RANKS, calculateRank } from '../ranking.js';
import { formatNumber } from '../helpers.js';
import { BACK_MENU } from '../keyboards.js';

const MEDALS = ['🥇', '🥈', '🥉'];

export async function showRanking(message) {
  const chatId = message.chat.id;
  const telegramId = message.from.id;
  const user = await getUserByTelegramId(telegramId);
  if (!user) return api.sendMessage({ chat_id: chatId, text: '⚠️ لطفاً ابتدا /start را بزنید.' });

  const rankKey = calculateRank(user.totalSpent || 0);
  const rankInfo = RANKS[rankKey];
  const order = ['bronze', 'silver', 'gold', 'platinum'];
  const idx = order.indexOf(rankKey);
  const next = order[idx + 1];

  let text = `🏆 **رتبه‌بندی شما**\n\n` +
    `${rankInfo.name}\n` +
    `💰 مجموع خرید: \`${formatNumber(user.totalSpent || 0)}\` تومان\n`;
  if (next) {
    const remain = RANKS[next].minSpent - (user.totalSpent || 0);
    text += `⬆️ تا ${RANKS[next].name}: \`${formatNumber(Math.max(0, remain))}\` تومان\n`;
  } else {
    text += `✨ شما بالاترین رتبه را دارید!\n`;
  }

  const refCount = await countReferrals(user.referralCode);
  text += `👥 تعداد زیرمجموعه: \`${refCount}\` نفر\n\n`;

  text += '🏅 **برترین کاربران:**\n';
  const top = await topSpenders(10);
  top.forEach((u, i) => {
    const medal = MEDALS[i] || `${i + 1}.`;
    const label = u.telegramId === telegramId ? '👈 شما' : `کاربر #${u.telegramId}`;
    text += `${medal} ${label} — \`${formatNumber(u.totalSpent || 0)}\` تومان\n`;
  });

  await api.sendMessage({ chat_id: chatId, text, parse_mode: 'Markdown', reply_markup: BACK_MENU });
}
