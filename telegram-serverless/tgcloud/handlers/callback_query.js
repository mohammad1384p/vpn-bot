// Top-level dispatcher for Telegram `callback_query` updates (inline button
// taps). Exact matches are tried first, then prefix ("foo:...") matches.
import { api } from 'sdk';
import * as start from '../lib/flows/start.js';
import * as services from '../lib/flows/services.js';
import * as shop from '../lib/flows/shop.js';
import * as packages from '../lib/flows/packages.js';
import * as payment from '../lib/flows/payment.js';
import * as renew from '../lib/flows/renew.js';
import * as ticket from '../lib/flows/ticket.js';
import * as contentLinks from '../lib/flows/contentLinks.js';
import * as adminUsers from '../lib/admin/users.js';
import * as adminSettings from '../lib/admin/settings.js';
import * as adminServers from '../lib/admin/servers.js';
import * as adminInbounds from '../lib/admin/inbounds.js';
import * as adminPackages from '../lib/admin/packages.js';
import * as adminDiscounts from '../lib/admin/discounts.js';
import * as adminAdmins from '../lib/admin/admins.js';
import * as adminTickets from '../lib/admin/tickets.js';
import * as adminDb from '../lib/admin/db.js';
import * as adminContentLinks from '../lib/admin/contentLinks.js';
import * as adminPayments from '../lib/admin/payments.js';

const EXACT_HANDLERS = {
  check_join: start.checkJoinCallback,
  back_to_main_menu: shop.backToMainMenu,
  back_to_services: services.backToServices,
  services_refresh: services.refreshServices,
  buy_free_config: shop.buyFreeConfig,
  copy_referral_link: shop.copyReferralLinkHandler,
  pay_card: shop.payCardHandler,
  custom_amount: packages.customAmount,
  apply_discount_purchase: payment.applyDiscountPurchase,
  skip_discount_purchase: payment.skipDiscountPurchase,
  apply_discount_renew: renew.applyDiscountRenew,
  skip_discount_renew: renew.skipDiscountRenew,
  my_tickets_back: ticket.myTicketsBack,
  servers_menu: adminServers.serversMenu,
  inbounds_menu: adminInbounds.inboundsMenu,
  inbound_done: adminInbounds.inboundDoneCallback,
  server_add: adminServers.serverAddCallback,
  pkg_add: adminPackages.pkgAddCallback,
  discount_add: adminDiscounts.discountAddCallback,
  admin_add: adminAdmins.adminAddCallback,
  cl_add: adminContentLinks.clAddCallback,
  db_export: adminDb.dbExportCallback,
  db_import: adminDb.dbImportCallback,
};

// Ordered [prefix, handler] pairs — first matching `data.startsWith(prefix)` wins.
// None of these prefixes are a leading substring of another, so order only
// matters for readability.
const PREFIX_HANDLERS = [
  ['check_join_content:', contentLinks.checkJoinContentCallback],
  ['check_join:', start.checkJoinCallback],
  ['select_pkg:', packages.selectPackage],
  ['select_renew:', renew.selectRenew],
  ['service_detail:', services.serviceDetail],
  ['copy_sub:', services.copySubLink],
  ['renew_service:', services.renewServiceRedirect],
  ['view_ticket:', ticket.viewTicket],
  ['reply_ticket:', ticket.replyTicketStart],
  ['close_ticket:', ticket.closeTicketUser],
  ['reveal_content:', contentLinks.revealContentCallback],
  ['approve_renew_', renew.approveRenew],
  ['approve_pay_', adminPayments.approvePayment],
  ['reject_pay_', adminPayments.rejectPayment],
  ['users_page:', adminUsers.usersPageCallback],
  ['user_detail:', adminUsers.userDetailCallback],
  ['toggle_block:', adminUsers.toggleBlockCallback],
  ['edit_balance:', adminUsers.editBalanceCallback],
  ['reset_test:', adminUsers.resetTestCallback],
  ['setting_edit:', adminSettings.settingEditCallback],
  ['server_detail:', adminServers.serverDetailCallback],
  ['server_test:', adminServers.serverTestCallback],
  ['server_toggle:', adminServers.serverToggleCallback],
  ['server_delete:', adminServers.serverDeleteCallback],
  ['inbound_server:', adminInbounds.inboundServerCallback],
  ['inbound_toggle:', adminInbounds.inboundToggleCallback],
  ['pkg_detail:', adminPackages.pkgDetailCallback],
  ['pkg_toggle:', adminPackages.pkgToggleCallback],
  ['pkg_delete:', adminPackages.pkgDeleteCallback],
  ['discount_detail:', adminDiscounts.discountDetailCallback],
  ['discount_toggle:', adminDiscounts.discountToggleCallback],
  ['discount_delete:', adminDiscounts.discountDeleteCallback],
  ['admin_detail:', adminAdmins.adminDetailCallback],
  ['admin_remove:', adminAdmins.adminRemoveCallback],
  ['admin_view_ticket:', adminTickets.adminViewTicketCallback],
  ['admin_reply_ticket:', adminTickets.adminReplyTicketStart],
  ['admin_close_ticket:', adminTickets.adminCloseTicketCallback],
  ['cl_detail:', adminContentLinks.clDetailCallback],
  ['cl_toggle:', adminContentLinks.clToggleCallback],
  ['cl_delete:', adminContentLinks.clDeleteCallback],
];

export default async function callbackQueryHandler(callback) {
  if (!callback || !callback.data) return;
  const { data } = callback;

  if (EXACT_HANDLERS[data]) {
    await EXACT_HANDLERS[data](callback);
    return;
  }
  for (const [prefix, handler] of PREFIX_HANDLERS) {
    if (data.startsWith(prefix)) {
      await handler(callback);
      return;
    }
  }
  // Unknown/stale callback (e.g. button from a message sent by a previous
  // bot version) — acknowledge so Telegram stops showing the loading spinner.
  try { await api.answerCallbackQuery({ callback_query_id: callback.id }); } catch { /* ignore */ }
}
