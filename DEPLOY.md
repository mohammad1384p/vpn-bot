# 🚀 راهنمای اجرای ربات روی سرور

این ربات با **Polling** کار می‌کند (نه webhook)، پس نه دامین لازم دارد، نه SSL، نه پورت باز.
تنها چیزی که لازم است: یک سرور لینوکسی + دسترسی خروجی به `api.telegram.org` و به آدرس پنل (Marzban/X-UI و …).

---

## ۰) ⚠️ اول امنیت: توکن‌ها لو رفته‌اند

توکن ربات و GitHub token در همین گفت‌وگو ارسال شده‌اند و باید **حتماً باطل و جایگزین** شوند:

| مورد | کار لازم |
|---|---|
| 🤖 توکن ربات | تلگرام → `@BotFather` → `/mybots` → رباتت → `API Token` → **Revoke** → توکن جدید بگیر |
| 🔑 GitHub PAT | GitHub → Settings → Developer settings → Personal access tokens → **Delete** |

توکن جدید را **فقط** در فایل `.env` روی سرور بگذار (هرگز در کد یا git).

---

## ۱) پیش‌نیازها

- سرور **Ubuntu 22.04 / 24.04** یا Debian 12 (حتی ۱ هسته / ۱ گیگ رم کافی است)
- دسترسی `root` یا `sudo`
- پایتون ۳.۱۰+ (اسکریپت خودکار نصب می‌کند)
- **`نکته حیاتی`**: اگر سرور داخل ایران است، تلگرام فیلتر است و ربات بالا نمی‌آید → بخش ۷ را بخوان.

---

## ۲) نصب در یک دستور (پیش‌فرض: مسیر `/opt/vpn-bot`)

روی سرور، به‌عنوان root اجرا کن:

```bash
curl -fsSL https://raw.githubusercontent.com/mohammad1384p/vpn-bot/main/deploy/setup.sh | sudo bash -s -- \
  --token "توکن_جدید_بات" \
  --admin-id "آیدی_عددی_تلگرام_خودت"
```

یا اگر ریپازیتوری private است و می‌خواهی کد را خودت بیاوری:

```bash
sudo -i
git clone https://github.com/mohammad1384p/vpn-bot.git /opt/vpn-bot
cd /opt/vpn-bot
sudo bash deploy/setup.sh          # توکن و آیدی ادمین را تعاملی می‌پرسد
```

اسکریپت این کارها را انجام می‌دهد:
1. نصب `python3`, `python3-venv`, `git`, `sqlite3`, `logrotate`
2. ساخت کاربر سیستمی `vpnbot` (بدان shell، محدود)
3. کلون/به‌روزرسانی کد در `/opt/vpn-bot`
4. ساخت `venv` و نصب `requirements.txt`
5. ساخت `/opt/vpn-bot/.env` با دسترسی `600`
6. نصب و فعال‌سازی سرویس `systemd` (اجرای خودکار بعد از ریبوت)
7. لاگ‌راتیت + بکاپ روزانه دیتابیس (cron ساعت ۰۳:۱۷)
8. استارت سرویس و نمایش وضعیت

---

## ۳) نصب دستی (اگر اسکریپت را نمی‌خواهی)

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git sqlite3

sudo useradd --system --home-dir /opt/vpn-bot --shell /usr/sbin/nologin vpnbot
sudo git clone https://github.com/mohammad1384p/vpn-bot.git /opt/vpn-bot
cd /opt/vpn-bot

sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt

# فایل تنظیمات
sudo nano /opt/vpn-bot/.env
#    BOT_TOKEN=توکن_جدید
#    ADMIN_ID=آیدی_عددی_خودت
sudo chmod 600 /opt/vpn-bot/.env
sudo chown -R vpnbot:vpnbot /opt/vpn-bot

# سرویس
sudo cp deploy/vpn-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vpn-bot
```

---

## ۴) مدیریت روزمره

```bash
sudo systemctl status vpn-bot          # وضعیت
sudo journalctl -u vpn-bot -f          # لاگ زنده (Ctrl+C برای خروج)
sudo journalctl -u vpn-bot --since "1 hour ago"   # لاگ یک ساعت اخیر
sudo systemctl restart vpn-bot         # ری‌استارت
sudo systemctl stop vpn-bot            # توقف
sudo systemctl disable vpn-bot         # غیرفعال کردن اجرای خودکار
```

آپدیت به آخرین نسخه (با بکاپ خودکار قبل از آپدیت):

```bash
sudo bash /opt/vpn-bot/deploy/update.sh
```

بکاپ دستی دیتابیس:

```bash
sudo /usr/local/sbin/vpn-bot-backup.sh      # خروجی: /var/backups/vpn-bot/vpn_bot_*.db.gz
```

> دیتابیس `vpn_bot.db` در ریپو هم هست، اما **منبع اصلی حقیقت روی سرور است**. بکاپ‌ها را گاهی به سیستم خودت منتقل کن.

---

## ۵) تنظیمات داخل ربات (بعد از بالا آمدن)

در تلگرام به رباتت `/start` بزن، سپس `/admin` و از منوی **⚙️ تنظیمات اولیه** این‌ها را کامل کن:

| بخش | مقدار |
|---|---|
| 🤖 نام کاربری ربات | بدون @ |
| 🌐 آدرس پنل | مثل `https://panel.example.com:54321/مسیر` |
| 🌐 API Token | توکن پنل |
| 🌍 سرورها | افزودن سرور(ها) و اولویت‌بندی |
| 🔗 الگوی لینک ساب | `https://domain.com:2096/sub/{subId}` |
| 💳 شماره کارت / نام صاحب کارت | برای پرداخت‌ها |
| 📢 آیدی کانال‌ها | عضویت اجباری |
| 📞 یوزرنیم پشتیبانی | — |
| 🧪 تنظیمات تست و 🎁 کانفیگ رایگان | طبق سیاست خودت |

تا وقتی «آدرس پنل»، «API Token» و حداقل یک «سرور» ثبت نشود، ربات پیام «تنظیمات اولیه تکمیل نشده» می‌دهد.

---

## ۶) چک‌لیست امنیت سرور

```bash
# فایروال: فقط SSH
sudo ufw allow OpenSSH && sudo ufw enable

# دسترسی فایل تنظیمات
sudo chmod 600 /opt/vpn-bot/.env

# توکن‌های قدیمی را Revoke کن (بخش ۰)
```

- ورود با رمز عبور را غیرفعال و از SSH key استفاده کن (`PasswordAuthentication no`).
- ربات با کاربر `vpnbot` اجرا می‌شود، نه root.
- `.env` در `.gitignore` است؛ هیچ‌وقت `git add .env` نکن.

---

## ۷) اگر سرور داخل ایران است (تلگرام فیلتر است)

دو راه ساده:

**الف) تونل SSH به یک سرور خارج (ساده‌ترین):**
```bash
sudo apt install -y autossh
# ساخت تونل socks5 روی پورت 1080 از طریق سرور خارج
autossh -M 0 -f -N -D 1080 user@سرور_خارج
```
سپس در `/opt/vpn-bot/.env` اضافه کن و سرویس را ری‌استارت کن:
```env
PROXY_URL=socks5://127.0.0.1:1080
```
(کتابخانه `aiohttp-socks` در `requirements.txt` است و کد به‌صورت خودکار از این متغیر استفاده می‌کند.)

**ب) استفاده از پروکسی HTTP خارجی:**
```env
PROXY_URL=http://user:pass@IP:PORT      # یا  http://IP:PORT
```

تست دسترسی بدون ربات:
```bash
curl -s -x socks5://127.0.0.1:1080 https://api.telegram.org | head -1
```

---

## ۸) عیب‌یابی

| خطا | علت و رفع |
|---|---|
| `TelegramNetworkError` / `Network is unreachable` | دسترسی به تلگرام نداری → بخش ۷ |
| `Unauthorized` | توکن اشتباه یا Revoke شده → توکن جدید در `.env` |
| `ADMIN_ID ... invalid literal for int()` | `ADMIN_ID` در `.env` خالی یا غیرعددی است؛ آیدی عددی از `@userinfobot` |
| `ModuleNotFoundError: No module named 'bot'` | با `python -m bot.main` از مسیر `/opt/vpn-bot` اجرا کن (سرویس این کار را می‌کند) |
| سرویس مدام ری‌استارت می‌شود | `journalctl -u vpn-bot -n 100` را ببین |
| ربات به پنل وصل نمی‌شود | آدرس پنل/توکن را در «⚙️ تنظیمات اولیه» چک کن؛ از سرور `curl` به آدرس پنل بزن |
| دیتابیس قفل شده | سرویس را stop کن، با `/usr/local/sbin/vpn-bot-backup.sh` بکاپ بگیر، دوباره start کن |

---

## ۹) فایل‌های این راهنما

```
deploy/
├── setup.sh            نصب کامل روی سرور
├── update.sh           آپدیت + ری‌استارت
├── backup_db.sh        بکاپ روزانه دیتابیس
└── vpn-bot.service     واحد systemd
.env.example            نمونه فایل تنظیمات
```
