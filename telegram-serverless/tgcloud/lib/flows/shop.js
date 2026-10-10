// Port of bot/handlers/shop.py
import { api, BotApiError } from 'sdk';
import { getUserByTelegramId, countReferrals, updateUser } from '../db/users.js';
import { getSetting } from '../db/settings.js';
import { getSelectedInboundIds } from '../db/settings.js';
import { createConfig, countActiveFreeConfigs, countOldFreeConfigs } from '../db/configs.js';
import { addClient } from '../panel.js';
import { requiresPhoneAuth } from './start.js';
import { PHONE_KB, MAIN_MENU } from '../keyboards.js';
import { setState } from '../state.js';
import { sendConfigPackage } from '../sendConfig.js';

async function getBotUsername() {
  const fromSettings = await getSetting('bot_username', '');
  if (fromSettings) return fromSettings;
  try {
    const me = await api.getMe();
    if (me && me.username) return me.username;
  } catch { /* ignore */ }
  return 'bot';
}

export async function showWallet(message) {
  const chatId = message.chat.id;
  const telegramId = message.from.id;
  try {
    const user = await getUserByTelegramId(telegramId);
    if (!user) return api.sendMessage({ chat_id: chatId, text: '⚠️ لطفاً ابتدا /start را بزنید.' });
    if (requiresPhoneAuth(user)) {
      return api.sendMessage({ chat_id: chatId, text: '🔐 چون با لینک زیرمجموعه وارد شده‌اید، برای مشاهده کیف پول ابتدا شماره تماس خود را تایید کنید.', reply_markup: PHONE_KB });
    }
    const refsCount = await countReferrals(user.referralCode);
    const freeThreshold = parseInt(await getSetting('free_config_threshold', '50000'), 10);
    const referralReward = parseInt(await getSetting('referral_reward', '10000'), 10);
    const botUsername = await getBotUsername();
    const referralLink = `https://t.me/${botUsername}?start=${user.referralCode}`;
    const text = '👛 **کیف پول شما:**\n' +
      `💰 موجودی: \`${(user.wallet || 0).toLocaleString('en-US')}\` تومان\n` +
      `👥 زیرمجموعه‌ها: \`${refsCount}\` نفر\n` +
      `🎁 پاداش هر زیرمجموعه: \`${referralReward.toLocaleString('en-US')}\` تومان\n` +
      `🎯 آستانه دریافت رایگان: \`${freeThreshold.toLocaleString('en-US')}\` تومان\n` +
      `🔗 **لینک دعوت شما:**\n\`${referralLink}\``;
    const kbButtons = [
      [{ text: '💳 افزایش موجودی', callback_data: 'pay_card' }],
      [{ text: '📋 کپی لینک دعوت', callback_data: 'copy_referral_link' },
        { text: '📤 اشتراک‌گذاری', switch_inline_query: `با لینک من رایگان VPN بگیر! 👇\n${referralLink}` }],
    ];
    if ((user.wallet || 0) >= freeThreshold) kbButtons.push([{ text: '🎁 دریافت کانفیگ رایگان', callback_data: 'buy_free_config' }]);
    await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kbButtons }, parse_mode: 'Markdown' });
  } catch (e) {
    console.error('Wallet Error', e);
    await api.sendMessage({ chat_id: chatId, text: '❌ خطایی در نمایش کیف پول رخ داد.' });
  }
}

export async function referralMenu(message) {
  const chatId = message.chat.id;
  const telegramId = message.from.id;
  try {
    const user = await getUserByTelegramId(telegramId);
    if (!user) return api.sendMessage({ chat_id: chatId, text: '⚠️ لطفاً ابتدا شماره تماس خود را ثبت کنید.' });
    const refsCount = await countReferrals(user.referralCode);
    const referralReward = parseInt(await getSetting('referral_reward', '10000'), 10);
    const botUsername = await getBotUsername();
    const referralLink = `https://t.me/${botUsername}?start=${user.referralCode}`;
    const text = '👥 **زیرمجموعه‌گیری:**\n' +
      `👥 تعداد زیرمجموعه‌ها: \`${refsCount}\` نفر\n` +
      `🎁 پاداش هر زیرمجموعه: \`${referralReward.toLocaleString('en-US')}\` تومان\n` +
      `🔗 **لینک اختصاصی شما:**\n\`${referralLink}\`\n` +
      '💡 **راهنما:**\n• لینک بالا را برای دوستان خود ارسال کنید\n• با هر ثبت‌نام و تایید شماره، پاداش به کیف پول شما اضافه می‌شود';
    const kbButtons = [
      [{ text: '📋 کپی لینک', callback_data: 'copy_referral_link' },
        { text: '📤 اشتراک‌گذاری', switch_inline_query: `با لینک من رایگان VPN بگیر! 👇\n${referralLink}` }],
      [{ text: '🔙 بازگشت به منو', callback_data: 'back_to_main_menu' }],
    ];
    await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kbButtons }, parse_mode: 'Markdown' });
  } catch (e) {
    console.error('Referral Error', e);
  }
}

export async function payCardHandler(callback) {
  await api.sendMessage({ chat_id: callback.message.chat.id, text: '💳 **افزایش موجودی**\nلطفاً مبلغ دلخواه خود را به تومان وارد کنید (حداقل ۱۰,۰۰۰ تومان):', parse_mode: 'Markdown' });
  await setState(callback.from.id, 'payment:waiting_for_amount', {});
  await api.answerCallbackQuery({ callback_query_id: callback.id });
}

export async function copyReferralLinkHandler(callback) {
  const user = await getUserByTelegramId(callback.from.id);
  if (!user) return api.answerCallbackQuery({ callback_query_id: callback.id, text: '❌ کاربر یافت نشد', show_alert: true });
  const botUsername = await getBotUsername();
  const referralLink = `https://t.me/${botUsername}?start=${user.referralCode}`;
  await api.sendMessage({ chat_id: callback.message.chat.id, text: `🔗 **لینک دعوت اختصاصی شما:**\n<code>${referralLink}</code>\n💡 _روی لینک بالا ضربه بزنید تا کپی شود._`, parse_mode: 'HTML' });
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '✅ لینک ارسال شد' });
}

export async function buyFreeConfig(callback) {
  const userId = callback.from.id;
  try { await api.answerCallbackQuery({ callback_query_id: callback.id, text: '⏳ در حال ساخت کانفیگ...' }); } catch { /* ignore */ }

  try {
    const user = await getUserByTelegramId(userId);
    const freeThreshold = parseInt(await getSetting('free_config_threshold', '50000'), 10);
    const freeVol = parseInt(await getSetting('free_config_volume_gb', '10'), 10);
    const freeDur = parseInt(await getSetting('free_config_duration_days', '30'), 10);

    const activeFreeCount = await countActiveFreeConfigs(userId);
    if (activeFreeCount >= 10) {
      return api.sendMessage({ chat_id: userId, text: '❌ شما ۱۰ سرویس رایگان فعال دارید. تا زمانی که آنها تمام نشوند، نمی‌توانید سرویس جدید بگیرید.' });
    }
    const oldFreeCount = await countOldFreeConfigs(userId);
    if (oldFreeCount > 0) {
      return api.sendMessage({ chat_id: userId, text: '❌ شما سرویس‌های رایگان منقضی شده یا قدیمی دارید که باید تعیین تکلیف شوند.' });
    }
    if (!user || (user.wallet || 0) < freeThreshold) {
      return api.sendMessage({ chat_id: userId, text: '❌ موجودی کافی نیست!' });
    }

    await updateUser(userId, { wallet: user.wallet - freeThreshold });

    const email = `free_${userId}_${Math.floor(Date.now() / 1000)}`;
    const selectedIds = await getSelectedInboundIds();
    const res = await addClient({
      email, totalGb: freeVol, expiryHours: freeDur * 24,
      inboundIds: selectedIds.length ? selectedIds : null,
    });

    if (res.success) {
      const inboundIdsStr = (res.inboundIds || []).join(',');
      await createConfig({
        telegramId: userId, username: email, subLink: res.subLink, subId: res.subId || null,
        isActive: true, expiryTime: res.expiryTimeMs || 0, serverId: res.serverId || 1,
        volumeGb: freeVol, durationDays: freeDur, inboundIds: inboundIdsStr,
      });
      await sendConfigPackage({ userId, subLink: res.subLink, username: email, volumeDisplay: `${freeVol} GB`, durationDisplay: `${freeDur} روز` });
      try { await api.sendMessage({ chat_id: callback.message.chat.id, text: '✅ کانفیگ رایگان شما ارسال شد.' }); } catch { /* ignore */ }
    } else {
      const refreshed = await getUserByTelegramId(userId);
      if (refreshed) await updateUser(userId, { wallet: (refreshed.wallet || 0) + freeThreshold });
      console.error('buy_free_config panel error', res.msg);
      await api.sendMessage({ chat_id: userId, text: `❌ خطا در ساخت کانفیگ: ${res.msg || 'خطای ناشناخته'}` });
    }
  } catch (e) {
    console.error('buy_free_config fatal', e);
    try { await api.sendMessage({ chat_id: userId, text: `❌ خطای داخلی: ${e.message || e}` }); } catch { /* ignore */ }
  }
}

export async function backToMainMenu(callback) {
  await api.sendMessage({ chat_id: callback.message.chat.id, text: 'منوی اصلی:', reply_markup: MAIN_MENU });
  await api.answerCallbackQuery({ callback_query_id: callback.id });
}
