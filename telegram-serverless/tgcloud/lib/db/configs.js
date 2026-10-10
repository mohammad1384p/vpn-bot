import { db } from 'sdk';
import { eq, and, desc, like, lt } from 'sdk/db';
import { configs } from '../../schema.js';

export async function createConfig(values) {
  const [row] = await db.insert(configs).values(values).returning().run();
  return row;
}

export async function getConfigById(id) {
  return await db.select().from(configs).where(eq(configs.id, id)).get();
}

export async function getConfigByIdForUser(id, telegramId) {
  return await db.select().from(configs).where(and(eq(configs.id, id), eq(configs.telegramId, telegramId))).get();
}

export async function listConfigsByUser(telegramId) {
  return await db.select().from(configs).where(eq(configs.telegramId, telegramId)).orderBy(desc(configs.id)).all();
}

export async function listRenewableConfigs(telegramId) {
  return await db.select().from(configs).where(and(eq(configs.telegramId, telegramId), eq(configs.isTest, false))).all();
}

export async function countActiveTestConfigs(telegramId) {
  return await db.$count(configs, and(eq(configs.telegramId, telegramId), eq(configs.isTest, true), eq(configs.isActive, true)));
}

export async function countActiveFreeConfigs(telegramId) {
  return await db.$count(configs, and(eq(configs.telegramId, telegramId), like(configs.username, 'free_%'), eq(configs.isActive, true)));
}

export async function countOldFreeConfigs(telegramId) {
  const dayMs = 24 * 60 * 60 * 1000;
  return await db.$count(configs, and(
    eq(configs.telegramId, telegramId), like(configs.username, 'free_%'), eq(configs.isActive, true),
    lt(configs.expiryTime, Date.now() - dayMs),
  ));
}

export async function updateConfig(id, patch) {
  await db.update(configs).set(patch).where(eq(configs.id, id)).run();
}

export async function deleteConfig(id) {
  await db.delete(configs).where(eq(configs.id, id)).run();
}

export async function countAll() {
  return await db.$count(configs);
}

export async function countActive(isTest) {
  return await db.$count(configs, and(eq(configs.isActive, true), eq(configs.isTest, isTest)));
}

export async function countInactive() {
  return await db.$count(configs, eq(configs.isActive, false));
}

export async function sampleActive(isTest, limit = 5) {
  return await db.select().from(configs).where(and(eq(configs.isActive, true), eq(configs.isTest, isTest)))
    .orderBy(desc(configs.expiryTime)).limit(limit).all();
}

export { configs };
