import { db } from 'sdk';
import { eq } from 'sdk/db';
import { settings } from '../../schema.js';

export async function getSetting(key, fallback = '') {
  const row = await db.select().from(settings).where(eq(settings.key, key)).get();
  return row ? row.value : fallback;
}

export async function setSetting(key, value) {
  await db.insert(settings).values({ key, value })
    .onConflictDoUpdate({ target: settings.key, set: { value } }).run();
}

export async function getChannelIds() {
  const raw = await getSetting('channel_ids', '');
  if (!raw) return [];
  return raw.split(',').map((s) => s.trim()).filter(Boolean).map((s) => parseInt(s, 10)).filter((n) => !Number.isNaN(n));
}

export async function getSelectedInboundIds() {
  const raw = await getSetting('selected_inbound_ids', '');
  if (!raw) return [];
  return raw.split(',').map((s) => s.trim()).filter(Boolean).map((s) => parseInt(s, 10));
}
