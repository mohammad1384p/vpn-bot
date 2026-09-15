# راهنمای اجرای بات روی سرور 🚀

این راهنما برای اجرای بات روی سرور لینوکسی (Ubuntu 20.04 / 22.04 / 24.04) نوشته شده است.

---

## پیش‌نیازها

| مورد | توضیح |
|---|---|
| توکن بات تلگرام | از [@BotFather](https://t.me/BotFather) با دستور `/newbot` بگیرید |
| آیدی عددی ادمین | از [@userinfobot](https://t.me/userinfobot) بگیرید |
| پنل VPN | آدرس `URL` و `API Key` پنل (بعداً از داخل ربات اضافه می‌شود) |

> ⚠️ **هشدار امنیتی:** هرگز توکن‌ها را در چت یا داخل کد پابلیک نفرستید. توکن را فقط در فایل `.env` روی سرور نگه دارید (این فایل در `.gitignore` است و وارد گیت نمی‌شود).

---

## ۱) نصب ابزارهای لازم

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git python3-dev build-essential libjpeg-dev zlib1g-dev libpng-dev libfreetype6-dev
```

> پکیج‌های `python3-dev` و `libjpeg-dev` و `zlib1g-dev` برای نصب کتابخانه‌ی `Pillow` (ساخت QR کد) لازم‌اند. بدون آن‌ها خطای `Failed to build 'Pillow'` می‌گیرید.

## ۲) دریافت کد روی سرور

اگر ریپو **خصوصی** است، با Personal Access Token گیت‌هاب کلون کنید:

```bash
git clone https://<GITHUB_TOKEN>@github.com/mohammad1384p/vpn-bot.git /root/vpn-bot
```

اگر ریپو **پابلیک** است:

```bash
git clone https://github.com/mohammad1384p/vpn-bot.git /root/vpn-bot
```

## ۳) ساخت محیط مجازی و نصب وابستگی‌ها

```bash
cd /root/vpn-bot
python3 -m venv venv
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt
```

> اگر قبلاً `venv` خراب ساخته‌اید (نصب ناقص مانده)، اول پاکش کنید و دوباره بسازید:
>
> ```bash
> cd /root/vpn-bot
> rm -rf venv
> python3 -m venv venv
> ./venv/bin/pip install --upgrade pip setuptools wheel
> ./venv/bin/pip install -r requirements.txt
> ```

## ۴) ساخت فایل تنظیمات `.env`

```bash
nano /root/vpn-bot/.env
```

محتوای فایل (مقادیر خودتان را جایگذاری کنید):

```env
BOT_TOKEN=1234567890:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_ID=123456789
```

- `BOT_TOKEN` → توکن ربات از BotFather
- `ADMIN_ID` → آیدی **عددی** تلگرام ادمین (از @userinfobot)

> بدون `ADMIN_ID` ربات اجرا نمی‌شود (مقدارش در کد `int()` می‌شود).

## ۵) اجرای تستی (برای چک کردن خطاها)

```bash
cd /root/vpn-bot
PYTHONPATH=/root/vpn-bot ./venv/bin/python bot/main.py
```

اگر لاگ `INFO` دیدید و خطایی نبود، یعنی همه‌چیز درست است. با `Ctrl+C` متوقفش کنید.

## ۶) اجرای دائمی با systemd (پیشنهاد شده)

فایل سرویس آماده در `deploy/vpnbot.service` داخل ریپو هست. نصبش کنید:

```bash
sudo cp /root/vpn-bot/deploy/vpnbot.service /etc/systemd/system/vpnbot.service
sudo systemctl daemon-reload
sudo systemctl enable vpnbot
sudo systemctl start vpnbot
```

### دستورهای مدیریت سرویس

```bash
sudo systemctl status vpnbot        # وضعیت ربات
sudo systemctl restart vpnbot       # ری‌استارت
sudo systemctl stop vpnbot          # توقف
sudo journalctl -u vpnbot -f        # مشاهده‌ی لاگ زنده
```

## ۷) راه‌اندازی اولیه داخل ربات

1. در تلگرام به ربات پیام `/start` بدهید.
2. چون `ADMIN_ID` شماست، پنل مدیریت را می‌بینید.
3. از بخش **سرورها / اینباندها**، پنل VPN خود را اضافه کنید:
   - `name` → اسم دلخواه سرور
   - `url` → آدرس پنل (مثل `https://panel.example.com:2053`)
   - `api_key` → کلید API پنل
4. پکیج‌ها/پلن‌ها را بسازید و درگاه پرداخت را تنظیم کنید.

---

## عیب‌یابی خطاهای رایج

### خطای `Failed to build 'Pillow'`

یعنی وابستگی‌های سیستمی نصب نیست یا `pip` قدیمی است. راه‌حل:

```bash
sudo apt update
sudo apt install -y python3-dev build-essential libjpeg-dev zlib1g-dev libpng-dev libfreetype6-dev
cd /root/vpn-bot
rm -rf venv
python3 -m venv venv
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt
```

### خطای `ModuleNotFoundError: No module named 'aiogram'`

یعنی مرحله‌ی `pip install -r requirements.txt` کامل نشده (معمولاً به‌خاطر همان خطای Pillow در بالا). بعد از رفع مشکل Pillow و نصب موفق، این خطا هم حل می‌شود. برای اطمینان:

```bash
cd /root/vpn-bot
./venv/bin/pip list | grep -i aiogram
PYTHONPATH=/root/vpn-bot ./venv/bin/python bot/main.py
```

---

## بک‌آپ خودکار

ربات هر ساعت از دیتابیس (`vpn_bot.db`) بک‌آپ می‌گیرد و برای ادمین تلگرام می‌فرستد، پس کافی است ربات به‌درستی اجرا شده باشد.

## آپدیت ربات به نسخه جدید

```bash
cd /root/vpn-bot
git pull
./venv/bin/pip install -r requirements.txt
sudo systemctl restart vpnbot
```
