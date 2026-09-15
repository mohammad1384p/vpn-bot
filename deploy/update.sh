#!/usr/bin/env bash
# آپدیت ربات روی سرور: pull + نصب وابستگی‌های جدید + ری‌استارت سرویس
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vpn-bot}"
BRANCH="${BRANCH:-main}"
APP_USER="${APP_USER:-vpnbot}"

if [[ "$(id -u)" -ne 0 ]]; then echo "❌ با sudo اجرا کن" >&2; exit 1; fi

cd "$APP_DIR"

echo "==> بکاپ قبل از آپدیت"
/usr/local/sbin/vpn-bot-backup.sh || true

echo "==> دریافت آخرین تغییرات"
git fetch --all --prune
git checkout "$BRANCH"
git pull --ff-only

echo "==> به‌روزرسانی وابستگی‌ها"
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q

chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> ری‌استارت سرویس"
systemctl daemon-reload
systemctl restart vpn-bot.service
sleep 3
systemctl --no-pager status vpn-bot.service | head -n 8
