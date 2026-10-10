import { db } from 'sdk';
import { eq, and, asc, desc } from 'sdk/db';
import { packages } from '../../schema.js';

export async function listActivePackages() {
  return await db.select().from(packages).where(eq(packages.isActive, true)).orderBy(asc(packages.sortOrder), asc(packages.price)).all();
}

export async function listAllPackages() {
  return await db.select().from(packages).orderBy(asc(packages.sortOrder), asc(packages.price)).all();
}

export async function listAllPackagesByIdDesc() {
  return await db.select().from(packages).orderBy(desc(packages.id)).all();
}

export async function getPackageById(id) {
  return await db.select().from(packages).where(eq(packages.id, id)).get();
}

export async function findMatchingPackage(volumeGb, durationDays) {
  return await db.select().from(packages)
    .where(and(eq(packages.volumeGb, volumeGb), eq(packages.durationDays, durationDays), eq(packages.isActive, true)))
    .orderBy(asc(packages.price)).get();
}

export async function createPackage(values) {
  const [row] = await db.insert(packages).values(values).returning().run();
  return row;
}

export async function updatePackage(id, patch) {
  await db.update(packages).set(patch).where(eq(packages.id, id)).run();
}

export async function deletePackage(id) {
  await db.delete(packages).where(eq(packages.id, id)).run();
}

export { packages };
