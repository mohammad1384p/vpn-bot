// Database schema for the Telegram-Serverless port of the VPN bot.
// Mirrors bot/database.py (SQLAlchemy models) from the polling (aiogram) version.
// NOTE: there are no foreign keys on this platform (PRAGMA foreign_keys is off and
// .references()/foreignKey() throw at declaration time) — relations below are
// logical only and must be respected in application code.
import { table, integer, text, boolean, json, index, sql } from 'sdk/db';

// Telegram users of the bot (customers).
export const users = table('users', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  telegramId: integer('telegram_id').unique().notNull(),
  phone: text('phone'),
  wallet: integer('wallet').default(0),
  referralCode: text('referral_code').unique().notNull(),
  referredBy: text('referred_by'),
  lastTestTime: integer('last_test_time', { mode: 'timestamp_ms' }),
  phoneVerified: boolean('phone_verified').default(false),
  isBlocked: boolean('is_blocked').default(false),
  rank: text('rank').default('bronze'),
  totalSpent: integer('total_spent').default(0),
}, (t) => ({
  telegramIdx: index('idx_users_telegram_id').on(t.telegramId),
  referredByIdx: index('idx_users_referred_by').on(t.referredBy),
}));

// Bot admins besides the bootstrapped super-admin (see lib/auth.js).
export const admins = table('admins', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  telegramId: integer('telegram_id').unique().notNull(),
  name: text('name'),
  role: text('role').default('admin'),
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
});

// Manual card-to-card payments awaiting admin approval.
export const payments = table('payments', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  telegramId: integer('telegram_id').notNull(),
  amount: integer('amount').notNull(),
  status: text('status').default('pending'), // pending | approved | rejected
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
  packageId: integer('package_id'),
  discountCode: text('discount_code'),
  discountAmount: integer('discount_amount').default(0),
  serverId: integer('server_id').default(1),
}, (t) => ({
  telegramIdx: index('idx_payments_telegram_id').on(t.telegramId),
  statusIdx: index('idx_payments_status').on(t.status),
}));

// VPN config profiles issued to users (purchased, renewed, test or free).
export const configs = table('configs', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  telegramId: integer('telegram_id').notNull(),
  username: text('username').unique().notNull(),
  subLink: text('sub_link').notNull(),
  subId: text('sub_id'),
  isActive: boolean('is_active').default(true),
  expiryTime: integer('expiry_time').default(0), // epoch milliseconds (panel convention), 0 = unlimited
  serverId: integer('server_id').default(1),
  volumeGb: integer('volume_gb').default(10),
  durationDays: integer('duration_days').default(30),
  inboundIds: text('inbound_ids'),
  isTest: boolean('is_test').default(false),
  usedTrafficBytes: integer('used_traffic_bytes').default(0),
  isUnlimitedVolume: boolean('is_unlimited_volume').default(false),
  isUnlimitedTime: boolean('is_unlimited_time').default(false),
  groupName: text('group_name'),
  lastVolumeWarningAt: integer('last_volume_warning_at', { mode: 'timestamp' }),
  lastExpiryWarningAt: integer('last_expiry_warning_at', { mode: 'timestamp' }),
}, (t) => ({
  telegramIdx: index('idx_configs_telegram_id').on(t.telegramId),
}));

// Free-form key/value configuration (panel URL, card number, help links, ...).
export const settings = table('settings', {
  key: text('key').primaryKey(),
  value: text('value').notNull(),
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
});

// Purchasable packages shown in the shop.
export const packages = table('packages', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull(),
  volumeGb: integer('volume_gb').default(0),
  durationDays: integer('duration_days').default(0),
  price: integer('price').notNull(),
  isActive: boolean('is_active').default(true),
  sortOrder: integer('sort_order').default(0),
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
});

// Support tickets.
export const tickets = table('tickets', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  telegramId: integer('telegram_id').notNull(),
  subject: text('subject').notNull(),
  status: text('status').default('open'), // open | admin_replied | closed
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
}, (t) => ({
  telegramIdx: index('idx_tickets_telegram_id').on(t.telegramId),
  statusIdx: index('idx_tickets_status').on(t.status),
}));

export const ticketMessages = table('ticket_messages', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  ticketId: integer('ticket_id').notNull(),
  senderId: integer('sender_id').notNull(),
  senderType: text('sender_type').notNull(), // user | admin
  text: text('text'),
  photoFileId: text('photo_file_id'),
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
}, (t) => ({
  ticketIdx: index('idx_ticket_messages_ticket_id').on(t.ticketId),
}));

export const discountCodes = table('discount_codes', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  code: text('code').unique().notNull(),
  percent: integer('percent').notNull(),
  maxUses: integer('max_uses').default(0),
  usedCount: integer('used_count').default(0),
  minAmount: integer('min_amount').default(0),
  expiresAt: integer('expires_at', { mode: 'timestamp' }),
  isActive: boolean('is_active').default(true),
  isFirstPurchase: boolean('is_first_purchase').default(false),
  isRenewal: boolean('is_renewal').default(false),
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
});

// VPN panel servers (multi-server support, same as panel_api.py).
export const servers = table('servers', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull(),
  url: text('url').notNull(),
  apiKey: text('api_key').notNull(),
  inboundId: integer('inbound_id').default(1),
  isActive: boolean('is_active').default(true),
  priority: integer('priority').default(1),
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
});

// Shareable "content" links (gated behind forced channel join), with optional ad.
export const contentLinks = table('content_links', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  code: text('code').unique().notNull(),
  title: text('title'),
  contentType: text('content_type').notNull(), // text|photo|document|video|audio|voice
  contentText: text('content_text'),
  contentFileId: text('content_file_id'),
  contentCaption: text('content_caption'),
  hasAd: boolean('has_ad').default(false),
  adText: text('ad_text'),
  adPhotoId: text('ad_photo_id'),
  createdBy: integer('created_by').notNull(),
  views: integer('views').default(0),
  isActive: boolean('is_active').default(true),
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
});

// Per-chat conversation state — replaces aiogram's FSMContext, since a
// serverless handler invocation is stateless between Telegram updates.
export const states = table('states', {
  telegramId: integer('telegram_id').primaryKey(),
  step: text('step').notNull(),
  data: json('data'),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
});
