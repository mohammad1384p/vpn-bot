#!/usr/bin/env bash
# اجرای دستی ربات (بدون systemd) — برای تست سریع
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
export PYTHONPATH="$APP_DIR:$APP_DIR/bot"
export PYTHONUNBUFFERED=1

PY="$APP_DIR/venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"

exec "$PY" -m bot.main
