#!/usr/bin/env bash
# بکاپ امن از دیتابیس SQLite (با دستور .backup تا در صورت درحال‌نوشتن بودن هم سالم باشد)
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vpn-bot}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/vpn-bot}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d_%H%M%S)"

if [[ -f "$APP_DIR/vpn_bot.db" ]]; then
  sqlite3 "$APP_DIR/vpn_bot.db" ".backup '$BACKUP_DIR/vpn_bot_$TS.db'"
  gzip -f "$BACKUP_DIR/vpn_bot_$TS.db"
  echo "✅ بکاپ: $BACKUP_DIR/vpn_bot_$TS.db.gz"
else
  echo "⚠️  دیتابیس پیدا نشد: $APP_DIR/vpn_bot.db"
fi

find "$BACKUP_DIR" -name 'vpn_bot_*.db.gz' -mtime +"$KEEP_DAYS" -delete
