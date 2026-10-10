// Static, deploy-time configuration.
//
// There is no environment-variable mechanism on Telegram Serverless (no
// filesystem, no process.env) — everything else the bot needs (panel URL,
// card number, channel ids, ...) lives in the `settings` table and is edited
// from inside the bot itself (see lib/admin/settings.js), exactly like the
// polling version's Setting model.
//
// The only two values that must exist before *anyone* has talked to the bot
// are handled without any file edit:
//   - The very first person to ever send /start is auto-promoted to
//     "super admin" and that fact is persisted in `settings.super_admin_id`.
//     See lib/auth.js -> bootstrapSuperAdmin().
//
// FREE_CONFIG_DEFAULTS mirrors the hard-coded fallbacks in shop.py.
export const FREE_CONFIG_DEFAULTS = {
  thresholdToman: 50000,
  volumeGb: 10,
  durationDays: 30,
};

// External QR-code image generator. Telegram's Bot API accepts a plain
// https:// URL for any photo field, so we never have to fetch/re-upload
// bytes ourselves (no filesystem, no Pillow available here).
export function qrCodeUrl(data, size = 400) {
  return `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&data=${encodeURIComponent(data)}`;
}
