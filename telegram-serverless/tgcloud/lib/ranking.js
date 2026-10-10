// Mirrors bot/handlers/ranking.py
export const RANKS = {
  bronze: { name: '🥉 برنز', minSpent: 0 },
  silver: { name: '🥈 نقره‌ای', minSpent: 100000 },
  gold: { name: '🥇 طلایی', minSpent: 500000 },
  platinum: { name: '💎 پلاتینیوم', minSpent: 2000000 },
};

export function calculateRank(totalSpent) {
  for (const key of ['platinum', 'gold', 'silver', 'bronze']) {
    if (totalSpent >= RANKS[key].minSpent) return key;
  }
  return 'bronze';
}
