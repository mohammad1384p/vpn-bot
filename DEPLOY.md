# راهنمای اجرای بات روی سرور 🚀

این راهنما قدم‌به‌قدم و از صفر، اجرای بات روی سرور لینوکسی (Ubuntu 20.04 / 22.04 / 24.04 / 26.04) را توضیح می‌دهد. کافی است مراحل را به ترتیب انجام دهید.

---

## پیش‌نیازها

| مورد | از کجا بگیرید |
|---|---|
| توکن بات تلگرام | از [@BotFather](https://t.me/BotFather) با دستور `/newbot` |
| آیدی عددی ادمین | از [@userinfobot](https://t.me/userinfobot) (فقط عدد) |
| پنل VPN | آدرس `URL` و `API Key` پنل (بعداً از داخل ربات اضافه می‌شود) |

> ⚠️ **هشدار امنیتی:** هرگز توکن‌ها را در چت، گروه یا داخل کد نفرستید. توکن فقط باید در فایل `.env` روی سرور باشد (این فایل در `.gitignore` است و وارد گیت نمی‌شود). اگر توکنی لو رفت، توکن گیت‌هاب را از تنظیمات گیت‌هاب **Delete** کنید و توکن ربات را با دستور `/revoke` در BotFather عوض کنید.

---

## ۱) نصب ابزارهای سیستمی

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git python3-dev build-essential libjpeg-dev zlib1g-dev libpng-dev libfreetype6-dev software-properties-common
```

> پکیج‌های `python3-dev` و `libjpeg-dev` و `zlib1g-dev` برای نصب کتابخانه‌ی `Pillow` (ساخت QR کد) لازم‌اند. بدون آن‌ها خطای `Failed to build 'Pillow'` می‌گیرید.

---

## ۲) بررسی نسخه‌ی پایتون (⚠️ مرحله‌ی مهم)

```bash
python3 --version
ls /usr/bin/python3*
```

- اگر نسخه **3.10 تا 3.12** است → عالی، بروید مرحله‌ی ۳.
- اگر نسخه **3.13 یا 3.14** است → نسخه‌های داخل `requirements.txt` برای این پایتون فایل آماده (wheel) ندارند و نصب شکست می‌خورد. پس اول **Python 3.12** را نصب کنید و بقیه‌ی مراحل را با آن انجام دهید:

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
python3.12 --version
```

> در ادامه‌ی راهنما هر جا `python3` دیدید، اگر سرورتان 3.13/3.14 بود به‌جایش `python3.12` بنویسید.

---

## ۳) دریافت کد روی سرور

اگر ریپو **خصوصی** است، با Personal Access Token گیت‌هاب کلون کنید (به‌جای `<GITHUB_TOKEN>` توکن خودتان):

```bash
git clone https://<GITHUB_TOKEN>@github.com/mohammad1384p/vpn-bot.git /root/vpn-bot
```

اگر ریپو **پابلیک** است:

```bash
git clone https://github.com/mohammad1384p/vpn-bot.git /root/vpn-bot
```

---

## ۴) ساخت محیط مجازی و نصب وابستگی‌ها

```bash
cd /root/vpn-bot
python3 -m venv venv
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt
```

> اگر سرورتان Python 3.13/3.14 دارد، خط دوم را این‌طور بزنید:
>
> ```bash
> python3.12 -m venv venv
> ```

در پایان باید چیزی شبیه `Successfully installed ...` ببینید. برای اطمینان:

```bash
./venv/bin/pip list | grep -Ei "aiogram|aiohttp|pillow"
```

باید هر سه (`aiogram` ،`aiohttp` ،`pillow`) در لیست باشند.

> اگر قبلاً یک `venv` خراب ساخته‌اید (نصب ناقص مانده)، پاکش کنید و دوباره بسازید:
>
> ```bash
> cd /root/vpn-bot
> rm -rf venv
> python3 -m venv venv            # یا python3.12 -m venv venv
> ./venv/bin/pip install --upgrade pip setuptools wheel
> ./venv/bin/pip install -r requirements.txt
> ```

---

## ۵) ساخت فایل تنظیمات `.env`

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
>
> در `nano` با `Ctrl+O` بعد `Enter` ذخیره کنید و با `Ctrl+X` خارج شوید.

---

## ۶) اجرای تستی (برای چک کردن خطاها)

```bash
cd /root/vpn-bot
PYTHONPATH=/root/vpn-bot ./venv/bin/python bot/main.py
```

اگر لاگ‌های `INFO` دیدید و خطایی نبود، یعنی همه‌چیز درست است. با `Ctrl+C` متوقفش کنید و بروید مرحله‌ی بعد.

---

## ۷) اجرای دائمی با systemd (پیشنهاد شده)

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
sudo journalctl -u vpnbot -f        # مشاهده‌ی لاگ زنده
sudo systemctl restart vpnbot       # ری‌استارت
sudo systemctl stop vpnbot          # توقف
```

> چون محیط مجازی همیشه در مسیر `/root/vpn-bot/venv` ساخته می‌شود، فرقی نمی‌کند با `python3` یا `python3.12` ساخته باشید — فایل سرویس بدون تغییر کار می‌کند.

---

## ۸) راه‌اندازی اولیه داخل ربات

1. در تلگرام به ربات پیام `/start` بدهید.
2. چون `ADMIN_ID` شماست، پنل مدیریت را می‌بینید.
3. از بخش **سرورها / اینباندها**، پنل VPN خود را اضافه کنید:
   - `name` → اسم دلخواه سرور
   - `url` → آدرس پنل (مثل `https://panel.example.com:2053`)
   - `api_key` → کلید API پنل
4. پکیج‌ها/پلن‌ها را بسازید و درگاه پرداخت را تنظیم کنید.

---

## عیب‌یابی خطاهای رایج

### خطای `Failed to build 'Pillow'` یا `Getting requirements to build wheel ... error`

**علت ۱ (رایج‌ترین):** پایتون سرور 3.13 یا 3.14 است و پکیج‌های قدیمی wheel آماده ندارند.
→ راه‌حل: [مرحله‌ی ۲](#۲-بررسی-نسخه‌ی-پایتون-️-مرحله‌ی-مهم) را انجام دهید و `venv` را با `python3.12` بسازید.

**علت ۲:** وابستگی‌های سیستمی نصب نیست یا `pip` قدیمی است. راه‌حل:

```bash
sudo apt update
sudo apt install -y python3-dev build-essential libjpeg-dev zlib1g-dev libpng-dev libfreetype6-dev
cd /root/vpn-bot
rm -rf venv
python3 -m venv venv            # یا python3.12 -m venv venv
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

### ربات اجرا می‌شود ولی جواب نمی‌دهد

لاگ زنده را ببینید:

```bash
sudo journalctl -u vpnbot -f
```

موارد رایج: اشتباه بودن `BOT_TOKEN`، خالی/اشتباه بودن `ADMIN_ID`، یا وصل نبودن اینترنت سرور به تلگرام.

---

## بک‌آپ خودکار

ربات هر ساعت از دیتابیس (`vpn_bot.db`) بک‌آپ می‌گیرد و برای ادمین تلگرام می‌فرستد، پس کافی است ربات به‌درستی اجرا شده باشد.

## آپدیت ربات به نسخه‌ی جدید

```bash
cd /root/vpn-bot
git pull
./venv/bin/pip install -r requirements.txt
sudo systemctl restart vpnbot
```
