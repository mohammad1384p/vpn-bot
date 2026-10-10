// Port of bot/handlers/start.py
import { api } from 'sdk';
import { MAIN_MENU, PHONE_KB } from '../keyboards.js';
import { checkUserMembership, joinKeyboard } from '../membership.js';
import { getUserByTelegramId, getUserByReferralCode, getUserByPhone, createUser, updateUser } from '../db/users.js';
import { getSetting } from '../db/settings.js';
import { isIranPhone, normalizePhone, formatPhoneDisplay } from '../helpers.js';
import { bootstrapSuperAdmin, isAdmin } from '../auth.js';

export function requiresPhoneAuth(user) {
  if (!user) return false;
  const isReferral = !!(user.referredBy && String(user.referredBy) !== String(user.telegramId));
  return isReferral && !user.phoneVerified;
}

export async function showMainMenu(chatId, telegramId, firstName, refCode = null) {
  const notJoined = await checkUserMembership(telegramId);
  if (notJoined.length) {
    await api.sendMessage({
      chat_id: chatId,
      text: '👋 برای استفاده از ربات، ابتدا در کانال‌های زیر عضو شوید:',
      reply_markup: joinKeyboard(notJoined, refCode ? `check_join:${refCode}` : 'check_join'),
    });
    return;
  }

  let user = await getUserByTelegramId(telegramId);
  if (!user) {
    user = await createUser({ telegramId, referredBy: refCode });
  } else if (refCode && !user.referredBy && refCode !== String(telegramId)) {
    await updateUser(telegramId, { referredBy: refCode });
    user = { ...user, referredBy: refCode };
  }

  if (requiresPhoneAuth(user)) {
    await api.sendMessage({
      chat_id: chatId,
      text: '🔐 **تکمیل ثبت‌نام زیرمجموعه:**\nچون با لینک زیرمجموعه وارد شده‌اید، برای فعال‌سازی حساب و دریافت هدیه خوش‌آمدگویی، لطفاً شماره تماس خود را تایید کنید.',
      reply_markup: PHONE_KB,
      parse_mode: 'Markdown',
    });
    return;
  }
  await api.sendMessage({
    chat_id: chatId,
    text: `سلام ${firstName || ''} عزیز! 👋\nاز منوی زیر انتخاب کنید:`,
    reply_markup: MAIN_MENU,
  });
}

export async function handleStart(message) {
  const telegramId = message.from.id;
  const chatId = message.chat.id;
  await bootstrapSuperAdmin(telegramId); // first-ever user becomes super admin; no-op afterwards
  const parts = (message.text || '').trim().split(/\s+/);
  const refCode = parts.length > 1 ? parts[1] : null;

  if (refCode && refCode.startsWith('content_')) {
    const { startContentLink } = await import('./contentLinks.js');
    await startContentLink(message, refCode);
    return;
  }

  if (refCode) {
    const user = await getUserByTelegramId(telegramId);
    if (!user) {
      await createUser({ telegramId, referredBy: refCode });
    } else if (!user.referredBy && refCode !== String(user.telegramId)) {
      await updateUser(telegramId, { referredBy: refCode });
    }
  }

  const notJoined = await checkUserMembership(telegramId);
  if (notJoined.length) {
    await api.sendMessage({
      chat_id: chatId,
      text: '👋 برای استفاده از ربات، در کانال‌های زیر عضو شوید:',
      reply_markup: joinKeyboard(notJoined, refCode ? `check_join:${refCode}` : 'check_join'),
    });
    return;
  }

  const user = await getUserByTelegramId(telegramId);
  if (user && user.isBlocked) {
    await api.sendMessage({
      chat_id: chatId,
      text: '⛔ **دسترسی شما مسدود شده است.**\nبرای رفع مسدودیت با پشتیبانی تماس بگیرید.',
      parse_mode: 'Markdown',
    });
    return;
  }

  await showMainMenu(chatId, telegramId, message.from.first_name, refCode);
}

export async function checkJoinCallback(callback) {
  const parts = callback.data.split(':');
  const refCode = parts.length > 1 ? parts[1] : null;
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '⏳ در حال بررسی...' });
  const notJoined = await checkUserMembership(callback.from.id);
  if (!notJoined.length) {
    await api.editMessageText({
      chat_id: callback.message.chat.id, message_id: callback.message.message_id,
      text: '✅ **عضویت تأیید شد!**\n\n🏠 منوی اصلی در زیر نمایش داده شده است.',
    });
    await showMainMenu(callback.message.chat.id, callback.from.id, callback.from.first_name, refCode);
  } else {
    await api.editMessageText({
      chat_id: callback.message.chat.id, message_id: callback.message.message_id,
      text: '⚠️ هنوز در تمام کانال‌ها عضو نشده‌اید:',
      reply_markup: joinKeyboard(notJoined, refCode ? `check_join:${refCode}` : 'check_join'),
    });
  }
}

export async function handleContact(message) {
  const chatId = message.chat.id;
  const telegramId = message.from.id;
  if (!message.contact || !message.contact.phone_number) {
    await api.sendMessage({ chat_id: chatId, text: '❌ شماره دریافت نشد.' });
    return;
  }
  const phone = message.contact.phone_number;
  if (!isIranPhone(phone)) {
    await api.sendMessage({ chat_id: chatId, text: '❌ **شماره غیر ایرانی!**\nفقط شماره‌های ایران پذیرفته می‌شود.', parse_mode: 'Markdown' });
    return;
  }
  const normalized = normalizePhone(phone);
  const displayPhone = formatPhoneDisplay(phone);
  let user = await getUserByTelegramId(telegramId);
  if (user && user.phoneVerified) {
    await api.sendMessage({ chat_id: chatId, text: '✅ شماره شما قبلاً تایید شده است.', reply_markup: MAIN_MENU });
    return;
  }
  const existing = await getUserByPhone(normalized);
  if (existing && existing.telegramId !== telegramId) {
    await api.sendMessage({ chat_id: chatId, text: '⚠️ این شماره قبلاً ثبت شده است.' });
    return;
  }
  let isNewVerify = false;
  if (existing && existing.telegramId === telegramId) {
    isNewVerify = !existing.phoneVerified;
    await updateUser(telegramId, { phone: normalized, phoneVerified: true });
    user = { ...existing, phone: normalized, phoneVerified: true };
  } else {
    isNewVerify = true;
    if (!user) {
      user = await createUser({ telegramId, phone: normalized, phoneVerified: true });
    } else {
      const patch = { phone: normalized, phoneVerified: true };
      if (!user.referralCode || user.referralCode.startsWith('manual_')) patch.referralCode = String(telegramId);
      await updateUser(telegramId, patch);
      user = { ...user, ...patch };
    }
  }

  if (isNewVerify && user.referredBy && user.referredBy !== String(user.telegramId)) {
    const refUser = await getUserByReferralCode(user.referredBy);
    if (refUser) {
      const reward = parseInt(await getSetting('referral_reward', '10000'), 10);
      await updateUser(refUser.telegramId, { wallet: (refUser.wallet || 0) + reward });
      try {
        await api.sendMessage({
          chat_id: refUser.telegramId,
          text: '🎉 **تبریک! زیرمجموعه جدید تایید شد.**\n' +
            `👤 کاربر \`${user.telegramId}\` شماره خود را تایید کرد.\n` +
            `💰 مبلغ \`${reward.toLocaleString('en-US')}\` تومان به کیف پول شما اضافه شد.`,
          parse_mode: 'Markdown',
        });
      } catch { /* user may have blocked the bot */ }
    }
  }

  await api.sendMessage({
    chat_id: chatId,
    text: `✅ **شماره شما با موفقیت تایید شد!**\n📞 \`${displayPhone}\`\nاکنون می‌توانید از تمامی امکانات ربات استفاده کنید.`,
    reply_markup: MAIN_MENU, parse_mode: 'Markdown',
  });
}

export async function adminVerifyUser(message) {
  if (!(await isAdmin(message.from.id))) return;
  const parts = (message.text || '').split(/\s+/);
  if (parts.length < 2) return api.sendMessage({ chat_id: message.chat.id, text: '❌ فرمت: `/verify_user [id] [phone]`', parse_mode: 'Markdown' });
  const userId = parseInt(parts[1], 10);
  const phone = parts[2] || `manual_${userId}`;
  let user = await getUserByTelegramId(userId);
  let isNewVerify = false;
  if (!user) {
    user = await createUser({ telegramId: userId, phone, phoneVerified: true });
    isNewVerify = true;
  } else if (!user.phoneVerified) {
    isNewVerify = true;
    await updateUser(userId, { phone, phoneVerified: true });
    user = { ...user, phone, phoneVerified: true };
  }
  if (isNewVerify && user.referredBy && user.referredBy !== String(user.telegramId)) {
    const refUser = await getUserByReferralCode(user.referredBy);
    if (refUser) {
      const reward = parseInt(await getSetting('referral_reward', '10000'), 10);
      await updateUser(refUser.telegramId, { wallet: (refUser.wallet || 0) + reward });
      try {
        await api.sendMessage({ chat_id: refUser.telegramId, text: `🎉 تبریک! زیرمجموعه شما (${user.telegramId}) توسط ادمین تایید شد.\n💰 مبلغ \`${reward.toLocaleString('en-US')}\` تومان به کیف پول شما اضافه شد.`, parse_mode: 'Markdown' });
      } catch { /* blocked */ }
    }
  }
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ کاربر \`${userId}\` تایید شد.`, parse_mode: 'Markdown' });
  try { await api.sendMessage({ chat_id: userId, text: '🎉 حساب شما تایید شد!', reply_markup: MAIN_MENU, parse_mode: 'Markdown' }); } catch { /* blocked */ }
}

export async function adminUnverifyUser(message) {
  if (!(await isAdmin(message.from.id))) return;
  const parts = (message.text || '').split(/\s+/);
  const userId = parseInt(parts[1], 10);
  if (Number.isNaN(userId)) return api.sendMessage({ chat_id: message.chat.id, text: '❌ فرمت: `/unverify_user [id]`', parse_mode: 'Markdown' });
  const user = await getUserByTelegramId(userId);
  if (user) await updateUser(userId, { phoneVerified: false });
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ تایید کاربر \`${userId}\` لغو شد.`, parse_mode: 'Markdown' });
}

export async function adminResetPhone(message) {
  if (!(await isAdmin(message.from.id))) return;
  const parts = (message.text || '').split(/\s+/);
  const userId = parseInt(parts[1], 10);
  if (Number.isNaN(userId)) return api.sendMessage({ chat_id: message.chat.id, text: '❌ فرمت: `/reset_phone [id]`', parse_mode: 'Markdown' });
  const user = await getUserByTelegramId(userId);
  if (user) await updateUser(userId, { phone: null, phoneVerified: false });
  await api.sendMessage({ chat_id: message.chat.id, text: `✅ شماره \`${userId}\` ریست شد.`, parse_mode: 'Markdown' });
  try { await api.sendMessage({ chat_id: userId, text: '🔄 شماره شما ریست شد.', reply_markup: PHONE_KB }); } catch { /* blocked */ }
}
