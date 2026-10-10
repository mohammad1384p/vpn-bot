// Small formatting / utility helpers. Mirrors bits of bot/utils/helpers.py,
// bot/handlers/services.py and bot/handlers/start.py. `crypto` is not
// guaranteed to exist in the V8 isolate, so ids are generated with Math.random.

export function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function randomHex(length = 16) {
  let out = '';
  while (out.length < length) out += Math.floor(Math.random() * 16).toString(16);
  return out.slice(0, length);
}

export function formatNumber(n) {
  return Math.round(n || 0).toLocaleString('en-US');
}

export function formatBytes(bytesVal) {
  if (!bytesVal || bytesVal <= 0) return '0 B';
  let v = bytesVal;
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  for (const unit of units) {
    if (v < 1024.0) return v >= 10 ? `${v.toFixed(1)} ${unit}` : `${v.toFixed(2)} ${unit}`;
    v /= 1024.0;
  }
  return `${v.toFixed(1)} PB`;
}

export function formatRemainingTime(expiryMs) {
  if (!expiryMs || expiryMs <= 0) return '♾️ نامحدود';
  const diffMs = expiryMs - Date.now();
  if (diffMs <= 0) return '⛔ منقضی';
  const diffHours = diffMs / (1000 * 3600);
  const diffDays = Math.floor(diffHours / 24);
  const remHours = Math.floor(diffHours % 24);
  if (diffDays > 0) return `⏱ ${diffDays} روز ${remHours} ساعت`;
  if (remHours > 0) return `⏱ ${remHours} ساعت`;
  const diffMinutes = Math.floor((diffMs / (1000 * 60)) % 60);
  return `⏱ ${diffMinutes} دقیقه`;
}

export function progressBar(percent, length = 10) {
  const filled = Math.max(0, Math.min(length, Math.round((percent / 100) * length)));
  return '█'.repeat(filled) + '░'.repeat(length - filled);
}

export function normalizePhone(phone) {
  if (!phone) return '';
  let digits = String(phone).replace(/\D/g, '');
  if (digits.startsWith('0') && digits.length === 11) digits = '98' + digits.slice(1);
  return digits;
}

export function isIranPhone(phone) {
  const digits = normalizePhone(phone);
  return digits.length === 12 && digits.startsWith('98') && digits[2] === '9';
}

export function formatPhoneDisplay(phone) {
  const digits = normalizePhone(phone);
  if (digits.length === 12) return `+${digits.slice(0, 2)} ${digits.slice(2, 5)} ${digits.slice(5, 8)} ${digits.slice(8)}`;
  return phone;
}

// Admin-list phone formatter (bot/handlers/admin.py format_phone) — accepts
// either an already-normalized "98..." string or a local "0..." string.
export function formatPhoneAdmin(phone) {
  if (!phone) return '❌';
  const digits = String(phone).replace(/\D/g, '');
  if (digits.length === 12 && digits.startsWith('98')) return `+${digits.slice(0, 2)} ${digits.slice(2, 5)} ${digits.slice(5, 8)} ${digits.slice(8)}`;
  if (digits.length === 11 && digits.startsWith('0')) return `+98 ${digits.slice(1, 4)} ${digits.slice(4, 7)} ${digits.slice(7)}`;
  return phone;
}

export function escapeHtml(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// NOTE: there is no setTimeout/timer API documented for this runtime, so
// unlike bot/handlers/admin.py (`asyncio.sleep(0.05)` between broadcast
// sends) we cannot throttle. See lib/admin/broadcast.js for the fallout.
