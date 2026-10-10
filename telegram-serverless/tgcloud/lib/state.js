// Conversation ("FSM") state, persisted in the `states` table.
//
// aiogram's FSMContext keeps per-chat state + a data dict in memory (or
// Redis); a serverless handler is a brand-new isolate per update, so the
// same thing has to live in the database between messages.
import { db } from 'sdk';
import { eq } from 'sdk/db';
import { states } from '../schema.js';

// Fetch { step, data } for a chat, or null when there is no active flow.
export async function getState(telegramId) {
  const row = await db.select().from(states).where(eq(states.telegramId, telegramId)).get();
  if (!row) return null;
  return { step: row.step, data: row.data || {} };
}

// Replace the state wholesale (step + full data object).
export async function setState(telegramId, step, data = {}) {
  await db.insert(states).values({ telegramId, step, data })
    .onConflictDoUpdate({ target: states.telegramId, set: { step, data } }).run();
}

// Merge `patch` into the existing data for the chat (creates the row if
// missing, keeping the current step or defaulting to '').
export async function updateStateData(telegramId, patch) {
  const current = await getState(telegramId);
  const merged = { ...(current?.data || {}), ...patch };
  await setState(telegramId, current?.step || '', merged);
  return merged;
}

export async function clearState(telegramId) {
  await db.delete(states).where(eq(states.telegramId, telegramId)).run();
}
