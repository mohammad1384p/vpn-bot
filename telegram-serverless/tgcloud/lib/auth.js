// Admin authorization. Mirrors bot/auth.py, but there is no Config.ADMIN_ID
// env var here — the "super admin" is bootstrapped automatically: the very
// first Telegram user who ever talks to the bot is promoted and that id is
// stored in settings.super_admin_id forever after.
import { db } from 'sdk';
import { eq } from 'sdk/db';
import { admins, users } from '../schema.js';
import { getSetting, setSetting } from './db/settings.js';

const SUPER_ADMIN_KEY = 'super_admin_id';

export async function getSuperAdminId() {
  const raw = await getSetting(SUPER_ADMIN_KEY, '');
  return raw ? parseInt(raw, 10) : null;
}

// Call this once per incoming update, before anything else that needs to
// know who the super admin is (start flow does this on every /start).
// If nobody is the super admin yet, the given user becomes it.
export async function bootstrapSuperAdmin(telegramId) {
  const existing = await getSuperAdminId();
  if (existing) return existing;
  await setSetting(SUPER_ADMIN_KEY, String(telegramId));
  return telegramId;
}

export async function isAdmin(telegramId) {
  const superId = await getSuperAdminId();
  if (superId && telegramId === superId) return true;
  const row = await db.select().from(admins).where(eq(admins.telegramId, telegramId)).get();
  return !!row;
}

export async function getAdminInfo(telegramId) {
  const superId = await getSuperAdminId();
  if (superId && telegramId === superId) {
    return { isSuper: true, role: 'super_admin', name: 'Super Admin' };
  }
  const row = await db.select().from(admins).where(eq(admins.telegramId, telegramId)).get();
  if (row) return { isSuper: false, role: row.role, name: row.name || `Admin ${telegramId}` };
  return null;
}

// All admin ids (super admin + admins table) — used to fan out
// notifications (new payment, new ticket message, ...).
export async function getAllAdminIds() {
  const superId = await getSuperAdminId();
  const rows = await db.select({ telegramId: admins.telegramId }).from(admins).all();
  const ids = rows.map((r) => r.telegramId);
  if (superId) ids.push(superId);
  return [...new Set(ids)];
}
