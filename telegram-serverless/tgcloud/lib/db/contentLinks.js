import { db } from 'sdk';
import { eq, desc, sql } from 'sdk/db';
import { contentLinks } from '../../schema.js';

export async function createContentLink(values) {
  const [row] = await db.insert(contentLinks).values(values).returning().run();
  return row;
}

export async function getContentLinkByCode(code) {
  return await db.select().from(contentLinks).where(eq(contentLinks.code, code)).get();
}

export async function getContentLinkById(id) {
  return await db.select().from(contentLinks).where(eq(contentLinks.id, id)).get();
}

export async function listContentLinks() {
  return await db.select().from(contentLinks).orderBy(desc(contentLinks.createdAt)).all();
}

export async function updateContentLink(id, patch) {
  await db.update(contentLinks).set(patch).where(eq(contentLinks.id, id)).run();
}

export async function deleteContentLink(id) {
  await db.delete(contentLinks).where(eq(contentLinks.id, id)).run();
}

export async function incrementViews(id) {
  await db.update(contentLinks).set({ views: sql`${contentLinks.views} + 1` }).where(eq(contentLinks.id, id)).run();
}

export { contentLinks };
