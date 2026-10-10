# VPN Bot — Telegram Serverless (tgcloud) port

This directory is a from-scratch **JavaScript** port of the existing Python
(aiogram + polling) VPN bot in the repository root, built for **Telegram
Serverless** (`tgcloud`) — the platform Telegram announced at
`core.telegram.org/bots/serverless`, where your bot's code runs as handler
functions in Telegram's own V8-isolate sandbox instead of a process you host
and poll with.

The deployable project lives in **`tgcloud/`**. Nothing in the Python bot at
the repository root was touched — the two bots are completely independent
and do **not** share a database, config, or any runtime state.

> This port could not be deployed or tested from the sandbox that built it:
> `tgcloud login`/`push`/`run` need a real bot token and network access to
> Telegram's infrastructure, which this environment does not have. The code
> was written strictly against the official `@tgcloud/cli` SDK reference
> (`tgcloud/docs/tgcloud-sdk.md`, bundled from the same npm package the real
> CLI ships), and every cross-module import was statically verified to
> resolve to a real export — but only you, running it with a live bot token,
> can confirm it behaves correctly end-to-end. Budget time for a shakedown
> pass per feature area after your first deploy.

## Why a separate folder instead of a separate branch

The work session this was built in is pinned to a single git branch and
cannot create or switch branches. A second top-level folder was used instead
so the two implementations stay cleanly separated without needing a second
branch — functionally equivalent to "a separate branch" for the purpose of
keeping the two bots from interfering with each other.

## Getting it running

```bash
cd telegram-serverless/tgcloud
npx @tgcloud/cli login     # link this project to a bot token you own
npx @tgcloud/cli push      # deploy schema.js, lib/, handlers/
npx @tgcloud/cli migrate   # apply the schema (first deploy + any later schema edits)
```

The platform auto-manages the Telegram webhook for you once handlers are
pushed. There is nothing to configure via environment variables (the
platform doesn't have any) — all bot configuration (panel server(s), card
number, forced-join channels, referral reward, free-config thresholds, help
links, etc.) is edited **from inside the bot itself** by an admin, via
"⚙️ تنظیمات اولیه" / "🖥 مدیریت سرورها" in the admin menu (`/admin`). This
mirrors the Python bot's `Setting` table, just without a `.env` file.

**The very first person to ever send `/start` to the bot becomes the super
admin automatically** (persisted as `settings.super_admin_id`) — there is no
`ADMIN_ID` to set beforehand. Make sure that's you.

## Project layout

```
tgcloud/
  schema.js            # all tables (sdk/db) — users, payments, configs, settings,
                        # packages, tickets, discountCodes, servers, contentLinks,
                        # admins, and a `states` table that replaces aiogram's FSM
  lib/
    config.js           # static constants + qrCodeUrl()
    auth.js             # super-admin bootstrap + admin lookups
    state.js            # per-chat conversation state (FSM replacement)
    panel.js            # 3x-ui/s-ui panel REST client (full port of panel_api.py)
    helpers.js          # formatting + uuidv4()/randomHex() (see Limitations)
    keyboards.js        # reply/inline keyboard constants
    membership.js       # forced-join channel check
    ranking.js           # spend-tier definitions
    sendConfig.js        # QR + sub-link delivery to the user, admin fan-out
    db/                  # one file per table — thin query helpers over sdk/db
    flows/                # user-facing features (1:1 with bot/handlers/*.py)
    admin/                # admin-only features (1:1 with the admin.py feature set)
  handlers/
    message.js            # top-level router for all incoming messages
    callback_query.js      # top-level router for all inline-button taps
  docs/tgcloud-sdk.md       # bundled copy of the official SDK reference
  AGENTS.md                  # bundled copy of tgcloud's project conventions
  tgcloud.jsonc, package.json, .gitignore
```

`handlers/message.js` and `handlers/callback_query.js` are intentionally the
*only* two files with "business logic routing" in them: they look up any
active conversation state first (`lib/state.js`), then match slash commands,
then reply-keyboard button text, and delegate everything else to the
`lib/flows/*` (user) or `lib/admin/*` (admin) module that implements it.

## Feature parity with the Python bot

Ported in full: onboarding + forced-join + referral codes + phone
verification, main menu, help/tutorial links, test accounts, the shop
(packages, custom-amount purchases, discount codes, card-to-card payment with
receipt photo + admin approve/reject), wallet + referral payouts + free
config redemption, "my services" with live panel traffic refresh, renewals
(with their own discount-code + payment flow and admin approval), the
spend-tier ranking/leaderboard, two-way support tickets, gated "content
links" (forced-join + optional ad screen before the content), multi-server
panel management + inbound selection, package/discount CRUD, sub-admin CRUD,
broadcast, a monitoring dashboard, aggregate financial reports, and a
database export/import tool.

A few admin wizards that were multi-prompt aiogram FSM chains in the Python
bot (e.g. "add a package", "add a server", "add a discount code") were
collapsed into **one message with several lines** (e.g. name/volume/duration/
price, one per line) instead of one prompt per field. This keeps
`lib/state.js`'s step list small and is a product simplification, not a
missing feature — every field is still editable.

## Limitations inherent to the platform (read before relying on this)

- **No cron / scheduled jobs.** The Python bot's hourly DB auto-backup and
  its 12-hour "check expiring services / send volume warnings" background
  loop (`bot/main.py`) have **no equivalent here** — Telegram Serverless only
  runs code in response to an incoming Telegram update (or a Mini App
  request), there is no timer/trigger mechanism. The closest replacements
  shipped in this port are **admin-triggered, on-demand** actions: "🖥
  مانیتورینگ" / "📊 گزارش‌ها" for a live snapshot, and "🗳 دیتابیس → 📤 خروجی
  JSON" for a manual backup. There is no automatic expiry/volume-warning
  push to users — it only happens passively, the next time the user opens
  "📦 سرویس‌های من" (which does refresh live traffic from the panel).
- **No environment variables or secrets.** Everything the Python bot reads
  from `.env`/`Config` (panel URL & key, admin id, card number, etc.) lives
  in the `settings` table here, edited from inside the bot. There's nothing
  to redeploy when you change it.
- **No `crypto` global and no `setTimeout`/timers** were found documented
  anywhere in the SDK reference, so this port never relies on either:
  `lib/helpers.js` implements its own `Math.random()`-based `uuidv4()` /
  `randomHex()` instead of `crypto.randomUUID()`, and the broadcast feature
  (`lib/admin/broadcast.js`) **cannot throttle sends** the way the Python
  bot does with `asyncio.sleep(0.05)` between messages. For a very large
  user base this means a broadcast may hit Telegram's rate limits (failed
  sends are just skipped, not retried) and/or run past a single handler
  invocation's execution-time budget — in which case it stops partway with
  no automatic resume, since there's also no cron to pick it back up.
- **Two completely separate databases.** This bot's SQLite database is
  fully managed by Telegram Serverless; it shares nothing with the Python
  bot's `vpn_bot.db`. Users, balances, configs, tickets — everything is
  independent between the two bots. Treat this as a fresh install.
- **QR codes are generated by an external HTTP API**
  (`api.qrserver.com`), not a local library — there is no filesystem and no
  npm packages on this platform, so Python/Pillow-style local QR generation
  isn't possible. `lib/config.js`'s `qrCodeUrl()` builds the image URL and
  it's passed straight to `sendPhoto`; Telegram's servers fetch it, so no
  bytes ever pass through the bot's own code. If you'd rather not depend on
  a third-party QR service, swap that one function for another provider.
- **No filesystem-based DB backup/restore.** The Python bot's backup command
  is a raw file copy of `vpn_bot.db`; that's not possible here, so
  `lib/admin/db.js` instead exports/imports a **JSON dump of every table**
  (sent/received as a Telegram document). A restore fully replaces every
  table's contents — read the confirmation prompt before using it on a live
  bot.
- **No automated testing in this environment.** The sandbox that built this
  code has no network path to Telegram or to a 3x-ui/s-ui panel, so nothing
  here has been run against live services. Every file was syntax-checked and
  every relative import was statically verified to resolve to a real,
  correctly-named export, but functional testing (sending `/start` for
  real, approving a real payment, etc.) is on you after your first deploy.

## A note on Markdown-escaping

A handful of places (ticket/support-ticket text, in particular) interpolate
free-form user/admin text into messages sent with `parse_mode: 'Markdown'`
without escaping Telegram's Markdown special characters. The Python bot has
the same property. It's unlikely to cause real problems (legacy "Markdown"
mode, unlike MarkdownV2, doesn't error out on most stray punctuation) but if
a user puts things like unmatched `` ` `` or `_` in a ticket message, the
resulting formatting can look odd. Not fixed here to stay scope-matched with
the original bot's behavior.
