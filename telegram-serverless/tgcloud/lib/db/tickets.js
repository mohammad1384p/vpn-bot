import { db } from 'sdk';
import { eq, and, desc, asc, ne } from 'sdk/db';
import { tickets, ticketMessages } from '../../schema.js';

export async function createTicket(values) {
  const [row] = await db.insert(tickets).values(values).returning().run();
  return row;
}

export async function getTicketById(id) {
  return await db.select().from(tickets).where(eq(tickets.id, id)).get();
}

export async function listTicketsByUser(telegramId) {
  return await db.select().from(tickets).where(eq(tickets.telegramId, telegramId)).orderBy(desc(tickets.updatedAt)).all();
}

export async function listOpenTicketsByUser(telegramId) {
  return await db.select().from(tickets).where(and(eq(tickets.telegramId, telegramId), ne(tickets.status, 'closed'))).all();
}

export async function listOpenTickets() {
  return await db.select().from(tickets).where(ne(tickets.status, 'closed')).orderBy(desc(tickets.updatedAt)).all();
}

export async function countOpenTickets() {
  return (await listOpenTickets()).length;
}

export async function updateTicket(id, patch) {
  await db.update(tickets).set({ ...patch, updatedAt: new Date() }).where(eq(tickets.id, id)).run();
}

export async function createTicketMessage(values) {
  const [row] = await db.insert(ticketMessages).values(values).returning().run();
  return row;
}

export async function listMessagesByTicket(ticketId) {
  return await db.select().from(ticketMessages).where(eq(ticketMessages.ticketId, ticketId)).orderBy(asc(ticketMessages.createdAt)).all();
}

export { tickets, ticketMessages };
