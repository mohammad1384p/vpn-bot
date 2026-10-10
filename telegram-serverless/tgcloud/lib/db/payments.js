import { db } from 'sdk';
import { eq, and, count, sum, sql } from 'sdk/db';
import { payments } from '../../schema.js';

export async function createPayment(values) {
  const [row] = await db.insert(payments).values(values).returning().run();
  return row;
}

export async function getPaymentById(id) {
  return await db.select().from(payments).where(eq(payments.id, id)).get();
}

export async function updatePayment(id, patch) {
  await db.update(payments).set(patch).where(eq(payments.id, id)).run();
}

export async function countApprovedByUser(telegramId) {
  return await db.$count(payments, and(eq(payments.telegramId, telegramId), eq(payments.status, 'approved')));
}

export async function countPending() {
  return await db.$count(payments, eq(payments.status, 'pending'));
}

export async function sumApprovedSince(sinceDate) {
  const row = await db.select({ total: sum(payments.amount) }).from(payments)
    .where(and(eq(payments.status, 'approved'), sql`${payments.createdAt} >= ${sinceDate}`)).get();
  return row?.total || 0;
}

export async function sumApprovedOnDate(dateStr) {
  const row = await db.get(sql`SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS cnt FROM payments WHERE status = 'approved' AND date(created_at, 'unixepoch') = ${dateStr}`);
  return { sum: row?.total || 0, count: row?.cnt || 0 };
}

export async function sumApprovedTotal() {
  const row = await db.select({ total: sum(payments.amount) }).from(payments).where(eq(payments.status, 'approved')).get();
  return row?.total || 0;
}

export async function sumApprovedByUser(telegramId) {
  const row = await db.select({ total: sum(payments.amount) }).from(payments)
    .where(and(eq(payments.telegramId, telegramId), eq(payments.status, 'approved'))).get();
  return row?.total || 0;
}

export { payments };
