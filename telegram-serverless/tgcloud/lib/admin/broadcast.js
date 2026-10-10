// Port of the broadcast part of bot/handlers/admin.py.
//
// IMPORTANT LIMITATION: the polling bot throttles broadcast sends with
// `asyncio.sleep(0.05)` between messages to stay under Bot API rate limits.
// Telegram Serverless documents no timer/sleep API, so this port cannot
// throttle — it fires sends back-to-back and simply tolerates/ignores
// individual failures (blocked bot, rate limit, etc). For very large user
// bases this may also run past a single invocation's execution-time budget,
// in which case the broadcast will stop partway with no automatic resume
// (there is no cron/background-task mechanism either). See the top-level
// README for details.
import { api } from 'sdk';
import { isAdmin } from '../auth.js';
import { allTelegramIds } from '../db/users.js';
import { setState, getState, clearState } from '../state.js';
import { ADMIN_MENU, CANCEL_MENU } from '../keyboards.js';

export async function broadcastStart(message) {
  if (!(await isAdmin(message.from.id))) return;
  await setState(message.from.id, 'admin:broadcast_waiting', {});
  await api.sendMessage({
    chat_id: message.chat.id,
    text: '📢 پیام همگانی را ارسال کنید (متن، عکس یا هر نوع پیام دیگر). این پیام برای تمام کاربران فوروارد خواهد شد.',
    reply_markup: CANCEL_MENU,
  });
}

export async function processBroadcast(message) {
  if (message.text === '❌ انصراف') {
    await clearState(message.from.id);
    return api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU });
  }
  await clearState(message.from.id);
  const ids = await allTelegramIds();
  await api.sendMessage({ chat_id: message.chat.id, text: `📢 شروع ارسال به ${ids.length} کاربر...` });

  let success = 0;
  let failed = 0;
  for (const id of ids) {
    try {
      await api.copyMessage({ chat_id: id, from_chat_id: message.chat.id, message_id: message.message_id });
      success += 1;
    } catch {
      failed += 1;
    }
  }
  await api.sendMessage({
    chat_id: message.chat.id,
    text: `✅ **پایان ارسال همگانی**\n✅ موفق: ${success}\n❌ ناموفق (مسدود/خطا): ${failed}`,
    reply_markup: ADMIN_MENU, parse_mode: 'Markdown',
  });
}
