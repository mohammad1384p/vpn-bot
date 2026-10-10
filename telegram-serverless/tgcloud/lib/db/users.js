import { db } from 'sdk';
import { eq, desc, gt } from 'sdk/db';
import { users } from '../../schema.js';

export async function getUserByTelegramId(telegramId) {
  return await db.select().from(users).where(eq(users.telegramId, telegramId)).get();
}

export async function getUserByReferralCode(code) {
  if (!code) return null;
  return await db.select().from(users).where(eq(users.referralCode, code)).get();
}

export async function getUserByPhone(phone) {
  if (!phone) return null;
  return await db.select().from(users).where(eq(users.phone, phone)).get();
}

export async function createUser({ telegramId, phone = null, phoneVerified = false, referredBy = null }) {
  const [row] = await db.insert(users).values({
    telegramId, phone, phoneVerified, referralCode: String(telegramId), referredBy, wallet: 0, rank: 'bronze', totalSpent: 0,
  }).returning().run();
  return row;
}

export async function countReferrals(referralCode) {
  return await db.$count(users, eq(users.referredBy, referralCode));
}

export async function topSpenders(limit = 10) {
  return await db.select().from(users).where(gt(users.totalSpent, 0)).orderBy(desc(users.totalSpent)).limit(limit).all();
}

export async function updateUser(telegramId, patch) {
  await db.update(users).set(patch).where(eq(users.telegramId, telegramId)).run();
}

export async function countUsers() {
  return await db.$count(users);
}

export async function listUsersPage(page, pageSize = 10) {
  return await db.select().from(users).orderBy(desc(users.id)).limit(pageSize).offset((page - 1) * pageSize).all();
}

export async function allTelegramIds() {
  const rows = await db.select({ telegramId: users.telegramId }).from(users).all();
  return rows.map((r) => r.telegramId);
}

export { users };
