#!/usr/bin/env bash
# ---------------------------------------------------------------
#  نصب/به‌روزرسانی ربات فروش VPN روی سرور (Ubuntu/Debian)
#  استفاده:
#     sudo bash deploy/setup.sh            # اجرای تعاملی (توکن و آیدی را می‌پرسد)
#     sudo BOT_TOKEN=... ADMIN_ID=... bash deploy/setup.sh
#     sudo bash deploy/setup.sh --dir /srv/vpn-bot --branch main
# ---------------------------------------------------------------
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vpn-bot}"
REPO_URL="${REPO_URL:-https://github.com/mohammad1384p/vpn-bot.git}"
BRANCH="${BRANCH:-main}"
APP_USER="${APP_USER:-vpnbot}"
BOT_TOKEN="${BOT_TOKEN:-}"
ADMIN_ID="${ADMIN_ID:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir)     APP_DIR="$2"; shift 2 ;;
    --repo)    REPO_URL="$2"; shift 2 ;;
    --branch)  BRANCH="$2"; shift 2 ;;
    --token)   BOT_TOKEN="$2"; shift 2 ;;
    --admin-id) ADMIN_ID="$2"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "آرگومان ناشناخته: $1" >&2; exit 1 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "❌ این اسکریپت باید با sudo/root اجرا شود: sudo bash $0" >&2
  exit 1
fi

echo "==> ۱/۸ نصب پیش‌نیازها"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl sqlite3 logrotate >/dev/null

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  echo "==> ۲/۸ ساخت کاربر سیستمی $APP_USER"
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
else
  echo "==> ۲/۸ کاربر $APP_USER از قبل وجود دارد"
fi

echo "==> ۳/۸ دریافت کد پروژه"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" checkout -B "$BRANCH" "origin/$BRANCH" 2>/dev/null || git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only || true
else
  mkdir -p "$APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

echo "==> ۴/۸ محیط مجازی پایتون و نصب وابستگی‌ها"
if [[ ! -x "$APP_DIR/venv/bin/python" ]]; then
  sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv" 2>/dev/null || python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --upgrade pip -q
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q

echo "==> ۵/۸ فایل محیطی .env"
if [[ ! -f "$APP_DIR/.env" ]]; then
  if [[ -z "$BOT_TOKEN" ]]; then
    read -rsp "توکن ربات (BOT_TOKEN): " BOT_TOKEN; echo
  fi
  if [[ -z "$ADMIN_ID" ]]; then
    read -rp "آیدی عددی ادمین (ADMIN_ID): " ADMIN_ID
  fi
  cat > "$APP_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_ID=$ADMIN_ID
# فقط در صورت نیاز (مثلاً سرور ایران): PROXY_URL=socks5://127.0.0.1:1080
# PROXY_URL=
EOF
  chmod 600 "$APP_DIR/.env"
  echo "   ✅ .env ساخته شد"
else
  chmod 600 "$APP_DIR/.env" || true
  echo "   ℹ️  .env موجود است، دست نخورده باقی ماند"
fi

# اگر دیتابیس در ریپو نباشد آن را با اجرای اولیه می‌سازیم؛ در غیر این صورت فقط مالکیت را تنظیم می‌کنیم
touch "$APP_DIR/vpn_bot.db" 2>/dev/null || true
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 750 "$APP_DIR"

echo "==> ۶/۸ نصب سرویس systemd"
UNIT_SRC="$APP_DIR/deploy/vpn-bot.service"
UNIT_DST="/etc/systemd/system/vpn-bot.service"
TMP_UNIT="$(mktemp)"
sed -e "s#/opt/vpn-bot#$APP_DIR#g" -e "s#^User=.*#User=$APP_USER#" -e "s#^Group=.*#Group=$APP_USER#" "$UNIT_SRC" > "$TMP_UNIT"
mv "$TMP_UNIT" "$UNIT_DST"
chmod 644 "$UNIT_DST"
systemctl daemon-reload
systemctl enable vpn-bot.service >/dev/null

echo "==> ۷/۸ لاگ‌راتیت و بکاپ روزانه"
cat > /etc/logrotate.d/vpn-bot <<'EOF'
/var/log/vpn-bot/*.log {
    daily
    rotate 7
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
}
EOF
mkdir -p /var/backups/vpn-bot
cp -f "$APP_DIR/deploy/backup_db.sh" /usr/local/sbin/vpn-bot-backup.sh
sed -i "s#^APP_DIR=.*#APP_DIR=\"$APP_DIR\"#" /usr/local/sbin/vpn-bot-backup.sh
chmod +x /usr/local/sbin/vpn-bot-backup.sh
cat > /etc/cron.d/vpn-bot <<'EOF'
# بکاپ روزانه دیتابیس ربات، هر شب ساعت 03:17
17 3 * * * root /usr/local/sbin/vpn-bot-backup.sh >/dev/null 2>&1
EOF
chmod 644 /etc/cron.d/vpn-bot

echo "==> ۸/۸ راه‌اندازی سرویس"
systemctl restart vpn-bot.service
sleep 3
systemctl --no-pager status vpn-bot.service | head -n 12 || true

cat <<EOF

────────────────────────────────────────────
✅ نصب تمام شد.
   مسیر پروژه : $APP_DIR
   وضعیت      : sudo systemctl status vpn-bot
   لاگ زنده   : sudo journalctl -u vpn-bot -f
   ری‌استارت  : sudo systemctl restart vpn-bot
   آپدیت      : sudo bash $APP_DIR/deploy/update.sh
────────────────────────────────────────────
EOF
