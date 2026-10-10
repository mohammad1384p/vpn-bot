// Top-level dispatcher for Telegram `message` updates.
//
// Routing order (mirrors aiogram's filter precedence in the polling bot):
//   1. Contact shares (phone verification button) — always handled first.
//   2. Slash commands — always take priority over any lingering FSM state.
//   3. An active FSM state (see lib/state.js) that expects a text/photo/
//      document reply — e.g. mid-payment, mid-ticket, mid-admin-wizard.
//   4. Known reply-keyboard button text.
//   5. Everything else is ignored (matches aiogram's default no-op).
import { api } from 'sdk';
import { getState, clearState } from '../lib/state.js';
import { isAdmin } from '../lib/auth.js';
import { MAIN_MENU, ADMIN_MENU } from '../lib/keyboards.js';
import * as start from '../lib/flows/start.js';
import * as help from '../lib/flows/help.js';
import * as test from '../lib/flows/test.js';
import * as services from '../lib/flows/services.js';
import * as shop from '../lib/flows/shop.js';
import * as packages from '../lib/flows/packages.js';
import * as payment from '../lib/flows/payment.js';
import * as renew from '../lib/flows/renew.js';
import * as discount from '../lib/flows/discount.js';
import * as ranking from '../lib/flows/ranking.js';
import * as ticket from '../lib/flows/ticket.js';
import * as adminMenu from '../lib/admin/menu.js';
import * as adminUsers from '../lib/admin/users.js';
import * as adminSettings from '../lib/admin/settings.js';
import * as adminServers from '../lib/admin/servers.js';
import * as adminPackages from '../lib/admin/packages.js';
import * as adminDiscounts from '../lib/admin/discounts.js';
import * as adminAdmins from '../lib/admin/admins.js';
import * as adminBroadcast from '../lib/admin/broadcast.js';
import * as adminTickets from '../lib/admin/tickets.js';
import * as adminReport from '../lib/admin/report.js';
import * as adminMonitoring from '../lib/admin/monitoring.js';
import * as adminDb from '../lib/admin/db.js';
import * as adminContentLinks from '../lib/admin/contentLinks.js';
import * as adminPayments from '../lib/admin/payments.js';

// Conversation-state step -> handler. Steps not listed here (e.g. the
// "*:cart" bookkeeping steps used while a purchase/renewal is still being
// composed via buttons) deliberately fall through to normal dispatch below.
const STATE_HANDLERS = {
  'payment:waiting_for_amount': payment.processAmount,
  'payment:waiting_for_discount_code': payment.processDiscountCode,
  'payment:waiting_for_receipt': payment.processReceipt,
  'renew:waiting_for_discount_code': renew.processDiscountCodeRenew,
  'renew:waiting_for_receipt': renew.processRenewReceipt,
  'ticket:waiting_subject': ticket.processSubject,
  'ticket:waiting_message': ticket.processFirstMessage,
  'ticket:waiting_reply': ticket.processUserReply,
  'admin:approve_custom_payment': adminPayments.processCustomPaymentApproval,
  'admin:user_search': adminUsers.processUserSearch,
  'admin:user_balance': adminUsers.processBalanceEdit,
  'admin:setting_value': adminSettings.processSettingValue,
  'admin:server_add': adminServers.processServerAdd,
  'admin:package_add': adminPackages.processPackageAdd,
  'admin:discount_add': adminDiscounts.processDiscountAdd,
  'admin:admin_add': adminAdmins.processAdminAdd,
  'admin:broadcast_waiting': adminBroadcast.processBroadcast,
  'admin:ticket_reply': adminTickets.processAdminTicketReply,
  'admin:db_import': adminDb.processDbImport,
  'admin:cl_waiting_content': adminContentLinks.processClContent,
  'admin:cl_waiting_meta': adminContentLinks.processClMeta,
  'admin:cl_waiting_ad': adminContentLinks.processClAd,
};

// Reply-keyboard button text -> handler.
const BUTTON_HANDLERS = {
  '🛒 خرید کانفیگ': packages.showPackages,
  '🔄 تمدید': renew.renewMenu,
  '📦 سرویس‌های من': (m) => services.myServicesMenu(m.chat.id, m.from.id),
  '🎁 اکانت تست': test.getTestAccount,
  '👥 کیف پول': shop.showWallet,
  '👥 زیرمجموعه‌گیری': shop.referralMenu,
  '🎓 راهنما': help.showHelpMenu,
  '🎫 پشتیبانی': ticket.showTicketMenu,
  '🏆 رتبه من': ranking.showRanking,
  '🎟 کد تخفیف': discount.showDiscountInfo,
  '🎫 تیکت جدید': ticket.newTicketStart,
  '📋 تیکت‌های من': ticket.myTickets,
  '🔙 بازگشت به منو': async (m) => start.showMainMenu(m.chat.id, m.from.id, m.from.first_name),
  '⚙️ تنظیمات اولیه': adminSettings.settingsMenu,
  '🖥 مانیتورینگ': adminMonitoring.showMonitoring,
  '💰 مالی': adminSettings.financialMenu,
  '📦 بسته‌ها': adminPackages.packagesMenu,
  '🎟 تخفیف‌ها': adminDiscounts.discountsMenu,
  '🎫 تیکت‌ها': adminTickets.ticketsMenu,
  '📢 لینک‌های محتوا': adminContentLinks.contentLinksMenu,
  '📊 گزارش‌ها': adminReport.showReport,
  '👥 کاربران': adminUsers.usersMenu,
  '👮 ادمین‌ها': adminAdmins.adminsMenu,
  '📢 همگانی': adminBroadcast.broadcastStart,
  '🗳 دیتابیس': adminDb.dbMenu,
};

async function handleCancelCommand(message) {
  const state = await getState(message.from.id);
  await clearState(message.from.id);
  const wasAdminFlow = !!(state && state.step && state.step.startsWith('admin:'));
  if (wasAdminFlow && (await isAdmin(message.from.id))) {
    await api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: ADMIN_MENU });
  } else {
    await api.sendMessage({ chat_id: message.chat.id, text: 'لغو شد.', reply_markup: MAIN_MENU });
  }
}

export default async function messageHandler(message) {
  if (!message || !message.from) return;

  if (message.contact) {
    await start.handleContact(message);
    return;
  }

  const text = message.text || '';
  if (text.startsWith('/')) {
    const cmd = text.split(/[\s@]/)[0];
    switch (cmd) {
      case '/start':
        await clearState(message.from.id);
        await start.handleStart(message);
        return;
      case '/cancel':
        await handleCancelCommand(message);
        return;
      case '/admin':
        await adminMenu.showAdminMenu(message);
        return;
      case '/verify_user':
        await start.adminVerifyUser(message);
        return;
      case '/unverify_user':
        await start.adminUnverifyUser(message);
        return;
      case '/reset_phone':
        await start.adminResetPhone(message);
        return;
      default:
        return; // unknown command, ignore (matches aiogram's default no-op)
    }
  }

  const state = await getState(message.from.id);
  if (state && STATE_HANDLERS[state.step]) {
    // A tap on a persistent reply-keyboard button always escapes whatever
    // wizard/FSM-state is pending — otherwise taps on the main/admin menu
    // while e.g. an "admin:user_search" or "payment:waiting_for_amount"
    // state is open would get silently swallowed as plain text input.
    if (text && BUTTON_HANDLERS[text]) {
      await clearState(message.from.id);
      await BUTTON_HANDLERS[text](message);
      return;
    }
    await STATE_HANDLERS[state.step](message);
    return;
  }

  if (text && BUTTON_HANDLERS[text]) {
    await BUTTON_HANDLERS[text](message);
    return;
  }

  if (help.isOsHelpButton(text)) {
    await help.showOsHelp(message);
    return;
  }

  // Anything else (random text/stickers/etc with no active flow) is ignored,
  // same as the polling bot's lack of a catch-all handler.
}
