import { db } from 'sdk';
import { eq, asc } from 'sdk/db';
import { servers } from '../../schema.js';

export async function listServers() {
  return await db.select().from(servers).orderBy(asc(servers.priority)).all();
}

export async function getServerById(id) {
  return await db.select().from(servers).where(eq(servers.id, id)).get();
}

export async function createServer(values) {
  const [row] = await db.insert(servers).values(values).returning().run();
  return row;
}

export async function updateServer(id, patch) {
  await db.update(servers).set(patch).where(eq(servers.id, id)).run();
}

export async function deleteServer(id) {
  await db.delete(servers).where(eq(servers.id, id)).run();
}

export { servers };
