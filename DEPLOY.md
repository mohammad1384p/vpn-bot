# راهنمای اجرای بات روی سرور 🚀

این راهنما قدم‌به‌قدم و از صفر، اجرای بات روی سرور لینوکسی (Ubuntu 20.04 / 22.04 / 24.04 / 26.04) را توضیح می‌دهد. کافی است مراحل را به ترتیب انجام دهید.

> 📁 **درباره‌ی مسیر پروژه:** این راهنما پروژه را در `/root/vpn-bot` فرض می‌کند، ولی همه‌ی دستورهای مهم با `$PWD` نوشته شده‌اند تا به مسیر وابسته نباشند. اگر پروژه را جای دیگری کلون کرده‌اید (مثلاً `/opt/vpn-bot`) فقط کافی است در همان مسیر کار کنید؛ فقط مرحله‌ی نصب سرویس systemd را طبق دستور ویژه‌ی همان مرحله انجام دهید.

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
sudo apt install -y python3 python3-venv python3-pip git python3-dev build-essential libjpeg-dev zlib1g-dev libpng-dev libfreetype6-dev
```

> پکیج‌های `python3-dev` و `libjpeg-dev` و `zlib1g-dev` برای نصب کتابخانه‌ی `Pillow` (ساخت QR کد) لازم‌اند. بدون آن‌ها خطای `Failed to build 'Pillow'` می‌گیرید.

---

## ۲) دریافت کد روی سرور

اگر ریپو **خصوصی** است، با Personal Access Token گیت‌هاب کلون کنید (به‌جای `<GITHUB_TOKEN>` توکن خودتان را بگذارید):

```bash
git clone https://<GITHUB_TOKEN>@github.com/mohammad1384p/vpn-bot.git /root/vpn-bot
```

اگر ریپو **پابلیک** است:

```bash
git clone https://github.com/mohammad1384p/vpn-bot.git /root/vpn-bot
```

> می‌توانید به‌جای `/root/vpn-bot` هر مسیر دیگری (مثلاً `/opt/vpn-bot`) بگذارید.

---

## ۳) ساخت محیط مجازی و نصب وابستگی‌ها

```bash
cd /root/vpn-bot        # یا مسیری که پروژه را کلون کرده‌اید
python3 -m venv venv
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt
```

در پایان باید چیزی شبیه `Successfully installed ...` ببینید. برای اطمینان:

```bash
./venv/bin/pip list | grep -Ei "aiogram|aiohttp|pillow|sqlalchemy"
```

باید همه‌ی موارد (`aiogram` ،`aiohttp` ،`pillow` ،`SQLAlchemy`) در لیست باشند.

> نسخه‌های داخل `requirements.txt` باز (range) هستند تا روی Python 3.10 تا 3.14 بدون مشکل نصب شوند؛ نسخه‌های تست‌شده: `aiogram 3.31.0` ،`aiohttp 3.14.5` ،`SQLAlchemy 2.1.8` ،`Pillow 13.0.0`.
>
> اگر قبلاً یک `venv` خراب ساخته‌اید (نصب ناقص مانده)، پاکش کنید و دوباره بسازید:
>
> ```bash
> cd /root/vpn-bot
> rm -rf venv
> python3 -m venv venv
> ./venv/bin/pip install --upgrade pip setuptools wheel
> ./venv/bin/pip install -r requirements.txt
> ```

---

## ۴) ساخت فایل تنظیمات `.env`

```bash
nano /root/vpn-bot/.env
```

محتوای فایل (مقادیر خودتان را جایگذاری کنید):

```env
BOT_TOKEN=1234567890:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_ID=123456789

# اختیاری: فقط وقتی سرور به api.telegram.org دسترسی ندارد (ایران/فیلترینگ)
# TELEGRAM_PROXY=socks5://127.0.0.1:1080
```

- `BOT_TOKEN` → توکن ربات از BotFather
- `ADMIN_ID` → آیدی **عددی** تلگرام ادمین (از @userinfobot)
- `TELEGRAM_PROXY` → (اختیاری) آدرس پروکسی SOCKS5/HTTP برای اتصال به تلگرام؛ مثل `socks5://127.0.0.1:1080` یا `http://user:pass@1.2.3.4:8080`

> بدون `ADMIN_ID` ربات اجرا نمی‌شود (مقدارش در کد `int()` می‌شود).
>
> در `nano` با `Ctrl+O` بعد `Enter` ذخیره کنید و با `Ctrl+X` خارج شوید.

---

## ۵) اجرای تستی (برای چک کردن خطاها)

```bash
cd /root/vpn-bot
PYTHONPATH=$PWD ./venv/bin/python bot/main.py
```

اگر لاگ‌های `INFO` دیدید و خطایی نبود، یعنی همه‌چیز درست است. با `Ctrl+C` متوقفش کنید و بروید مرحله‌ی بعد.

> ⚠️ `PYTHONPATH` حتماً باید به **ریشه‌ی پروژه** (پوشه‌ای که `bot/` داخل آن است) اشاره کند. استفاده از `$PWD` این کار را خودکار می‌کند. اگر مسیر را اشتباه بنویسید (مثلاً پروژه در `/opt/vpn-bot` باشد ولی `PYTHONPATH=/root/vpn-bot` بدهید) خطای `ModuleNotFoundError: No module named 'bot'` می‌گیرید.

---

## ۶) اجرای دائمی با systemd (پیشنهاد شده)

با این دستورات، فایل سرویس مستقیم ساخته می‌شود (نیازی به فایل `deploy/vpnbot.service` نیست و مسیر پروژه هر جا که باشد درست جایگزین می‌شود):

```bash
cd /root/vpn-bot        # بروید داخل پوشه‌ی پروژه (هر مسیری که هست، مثلاً /opt/vpn-bot)
sudo rm -f /etc/systemd/system/vpnbot.service
sudo systemctl unmask vpnbot
sudo tee /etc/systemd/system/vpnbot.service > /dev/null <<EOF
[Unit]
Description=VPN Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
Environment=PYTHONPATH=$(pwd)
ExecStart=$(pwd)/venv/bin/python bot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable vpnbot
sudo systemctl start vpnbot
```

> دقت کنید `EOF` آخر بدون `''` نوشته شده تا `$(pwd)` همان لحظه با مسیر واقعی پروژه جایگزین شود. دستورات را **دقیقاً از داخل پوشه‌ی پروژه** اجرا کنید.
>
> اگر فایل `deploy/vpnbot.service` داخل ریپو دارید، روش جایگزین:
>
> ```bash
> sudo sed "s|/root/vpn-bot|$(pwd)|g" deploy/vpnbot.service | sudo tee /etc/systemd/system/vpnbot.service
> sudo systemctl daemon-reload
> sudo systemctl enable vpnbot
> sudo systemctl start vpnbot
> ```

### دستورهای مدیریت سرویس

```bash
sudo systemctl status vpnbot        # وضعیت ربات
sudo journalctl -u vpnbot -f        # مشاهده‌ی لاگ زنده
sudo systemctl restart vpnbot       # ری‌استارت
sudo systemctl stop vpnbot          # توقف
```

---

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

### خطای `ModuleNotFoundError: No module named 'bot'`

یعنی `PYTHONPATH` به ریشه‌ی پروژه اشاره نمی‌کند. `PYTHONPATH` باید پوشه‌ای باشد که `bot/` داخل آن است:

```bash
cd /opt/vpn-bot                     # بروید داخل پوشه‌ی پروژه‌ی خودتان
PYTHONPATH=$PWD ./venv/bin/python bot/main.py
```

یعنی اگر پروژه در `/opt/vpn-bot` است، `PYTHONPATH` باید `/opt/vpn-bot` باشد (نه `/root/vpn-bot`). برای سرویس systemd هم از دستور `sed` مرحله‌ی ۶ استفاده کنید تا مسیرها درست شوند.

### خطای `Failed to build 'Pillow'` یا `Getting requirements to build wheel ... error`

**علت ۱:** وابستگی‌های سیستمی نصب نیست. راه‌حل:

```bash
sudo apt update
sudo apt install -y python3-dev build-essential libjpeg-dev zlib1g-dev libpng-dev libfreetype6-dev
cd /root/vpn-bot
rm -rf venv
python3 -m venv venv
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt
```

**علت ۲:** نسخه‌ی پایتون خیلی جدید است و پکیج پین‌شده wheel آماده ندارد (فقط وقتی `requirements.txt` نسخه‌ی قفل‌شده مثل `Pillow==10.2.0` داشته باشد). با `requirements.txt` فعلی (نسخه‌های باز) این مشکل نباید پیش بیاید؛ اگر باز هم خطا گرفتید، `venv` را با Python 3.12 بسازید:

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
cd /root/vpn-bot
rm -rf venv
python3.12 -m venv venv
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt
```

> مسیر `venv` عوض نمی‌شود، پس فایل سرویس systemd بدون تغییر کار می‌کند.

### خطای `ModuleNotFoundError: No module named 'aiogram'`

یعنی مرحله‌ی `pip install -r requirements.txt` کامل نشده (معمولاً به‌خاطر همان خطای Pillow در بالا). بعد از رفع مشکل و نصب موفق، این خطا هم حل می‌شود. برای اطمینان:

```bash
cd /root/vpn-bot
./venv/bin/pip list | grep -i aiogram
PYTHONPATH=$PWD ./venv/bin/python bot/main.py
```

### خطای `ImportError: The SQLAlchemy asyncio module requires ... 'greenlet'`

نصب وابستگی‌ها کامل نبوده (مثلاً پکیج‌ها را دستی یا بدون `-r requirements.txt` نصب کرده‌اید و extra‌های لازم جا افتاده‌اند). کافی است:

```bash
cd /root/vpn-bot
./venv/bin/pip install "sqlalchemy[asyncio]" aiohttp-socks
```

(در `requirements.txt` فعلی این مورد لحاظ شده و با نصب معمولی پیش نمی‌آید.)

### خطای `status=203/EXEC` در journalctl

یعنی systemd نتوانسته فایل اجرایی `ExecStart` را پیدا کند — معمولاً چون دستور `cd` به پوشه‌ی پروژه موفق نبوده (مثلاً `Permission denied`) و `$(pwd)` مسیر اشتباهی ساخته است. با دستورات زیر فایل سرویس را با مسیر ثابت بازنویسی کنید (به‌جای `/opt/vpn-bot` مسیر واقعی پروژه‌ی خودتان را بگذارید):

```bash
ls -la /opt/vpn-bot/venv/bin/python    # اول مطمئن شوید این فایل وجود دارد
sudo rm -f /etc/systemd/system/vpnbot.service
sudo tee /etc/systemd/system/vpnbot.service > /dev/null <<'EOF'
[Unit]
Description=VPN Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/vpn-bot
Environment=PYTHONPATH=/opt/vpn-bot
ExecStart=/opt/vpn-bot/venv/bin/python bot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl restart vpnbot
sudo journalctl -u vpnbot -f
```

> اگر `cd /opt/vpn-bot` خطای `Permission denied` می‌دهد، یعنی با کاربر غیر root وارد شده‌اید؛ اول `sudo -i` بزنید یا همه‌ی دستورها را با `sudo` اجرا کنید.

### خطای `Unit file ... is masked` یا `sed: can't read deploy/vpnbot.service`

یعنی فایل سرویس قبلاً خراب/masked شده یا فایل `deploy/vpnbot.service` داخل چک‌اوت شما نیست. با دستورات مرحله‌ی ۶ (روش heredoc) مشکل حل می‌شود؛ آن دستورات اول `rm -f` و `unmask` را انجام می‌دهند و بعد فایل سرویس را از نو می‌سازند.

### خطای `TelegramNetworkError: Request timeout error`

یعنی سرور نمی‌تواند به `api.telegram.org` وصل شود. اول مشخص کنید مشکل از چیست:

```bash
# باید در کمتر از ۱۰ ثانیه عدد 404 برگرداند (یعنی اتصال برقرار است)
curl -m 10 -sS -o /dev/null -w "%{http_code}\n" https://api.telegram.org/

# اگر بالایی timeout خورد، IPv4 را جدا امتحان کنید
curl -4 -m 10 -sS -o /dev/null -w "%{http_code}\n" https://api.telegram.org/
```

- اگر فقط دستور اول timeout خورد ولی `curl -4` جواب داد → مشکل **IPv6 خراب** است؛ کد فعلی ربات IPv4 را اجباری می‌کند و مشکل حل می‌شود (کافی است نسخه‌ی جدید را `git pull` کنید).
- اگر **هر دو** timeout خوردند → سرور به تلگرام دسترسی ندارد (فیلترینگ/مسدودسازی). باید از **پروکسی** استفاده کنید:

1. روی سرور یک پروکسی SOCKS5 بالا بیاورید (مثلاً تانل SSH):

   ```bash
   ssh -f -N -D 1080 user@سرور-خارجی
   ```

2. در فایل `.env` اضافه کنید و ربات را ری‌استارت کنید:

   ```env
   TELEGRAM_PROXY=socks5://127.0.0.1:1080
   ```

   ```bash
   sudo systemctl restart vpnbot
   ```

> خطای `Unclosed client session` فقط یک هشدار تمیزکاری هنگام خروج است و ریشه‌ی مشکل نیست؛ در نسخه‌ی جدید کد رفع هم شده.

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
