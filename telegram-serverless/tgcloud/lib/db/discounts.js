import { db } from 'sdk';
import { eq, desc } from 'sdk/db';
import { discountCodes } from '../../schema.js';

export async function getDiscountByCode(code) {
  return await db.select().from(discountCodes).where(eq(discountCodes.code, code)).get();
}

export async function getDiscountById(id) {
  return await db.select().from(discountCodes).where(eq(discountCodes.id, id)).get();
}

export async function listDiscounts() {
  return await db.select().from(discountCodes).orderBy(desc(discountCodes.createdAt)).all();
}

export async function createDiscount(values) {
  const [row] = await db.insert(discountCodes).values(values).returning().run();
  return row;
}

export async function updateDiscount(id, patch) {
  await db.update(discountCodes).set(patch).where(eq(discountCodes.id, id)).run();
}

export async function deleteDiscount(id) {
  await db.delete(discountCodes).where(eq(discountCodes.id, id)).run();
}

export async function incrementUsage(id, currentUsed) {
  await db.update(discountCodes).set({ usedCount: currentUsed + 1 }).where(eq(discountCodes.id, id)).run();
}

// Validate a code against an amount / purchase context, returns { ok, dc, error }.
// `isRenewal` and `isFirstPurchaseCheck` mirror payment.py / renew.py rules.
export async function validateDiscountCode(code, amount, { forRenewal = false, hasApprovedPayment = null } = {}) {
  const dc = await getDiscountByCode(code);
  if (!dc || !dc.isActive) return { ok: false, error: '❌ کد نامعتبر است. لطفاً مجدداً تلاش کنید یا /cancel را بزنید.' };
  if (dc.expiresAt && new Date(dc.expiresAt).getTime() < Date.now()) return { ok: false, error: '❌ کد منقضی شده است.' };
  if (dc.maxUses > 0 && dc.usedCount >= dc.maxUses) return { ok: false, error: '❌ ظرفیت این کد تمام شده است.' };
  if (forRenewal) {
    if (dc.isFirstPurchase) return { ok: false, error: '❌ این کد فقط برای **اولین خرید** معتبر است.' };
  } else {
    if (dc.isFirstPurchase && hasApprovedPayment) return { ok: false, error: '❌ این کد فقط برای **اولین خرید** معتبر است.' };
    if (dc.isRenewal) return { ok: false, error: '❌ این کد فقط برای **تمدید** معتبر است.' };
  }
  if (amount < dc.minAmount) return { ok: false, error: `❌ حداقل مبلغ برای این کد \`${dc.minAmount.toLocaleString('en-US')}\` تومان است.` };
  return { ok: true, dc };
}

export { discountCodes };
