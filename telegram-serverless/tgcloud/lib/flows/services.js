// Port of bot/handlers/services.py
import { api } from 'sdk';
import { getUserByTelegramId } from '../db/users.js';
import { listConfigsByUser, getConfigByIdForUser, updateConfig } from '../db/configs.js';
import { getClientTraffic } from '../panel.js';
import { requiresPhoneAuth } from './start.js';
import { PHONE_KB } from '../keyboards.js';
import { formatBytes, formatRemainingTime } from '../helpers.js';

async function updateConfigTrafficFromPanel(config) {
  if (!config.username || !config.serverId) return null;
  const res = await getClientTraffic(config.username, config.serverId);
  if (res.success) {
    const patch = { usedTrafficBytes: res.used || 0 };
    if (res.expiryTime) patch.expiryTime = res.expiryTime;
    const nowMs = Date.now();
    if (res.expiryTime && res.expiryTime !== 0 && res.expiryTime < nowMs) patch.isActive = false;
    else if (res.enable === false) patch.isActive = false;
    await updateConfig(config.id, patch);
    Object.assign(config, patch);
    return res;
  }
  return null;
}

export async function myServicesMenu(chatId, telegramId) {
  const user = await getUserByTelegramId(telegramId);
  if (!user) return api.sendMessage({ chat_id: chatId, text: '⚠️ لطفاً ابتدا /start را بزنید.' });
  if (requiresPhoneAuth(user)) {
    return api.sendMessage({ chat_id: chatId, text: '🔐 چون با لینک زیرمجموعه وارد شده‌اید، ابتدا شماره تماس خود را تایید کنید.', reply_markup: PHONE_KB });
  }
  const configsList = await listConfigsByUser(telegramId);
  if (!configsList.length) {
    return api.sendMessage({ chat_id: chatId, text: '📦 **سرویس‌های شما:**\n⚠️ هنوز سرویسی ندارید.', parse_mode: 'Markdown' });
  }

  let text = '📦 **سرویس‌های فعال شما:**\n';
  const kbButtons = [];
  let hasActive = false;
  for (const config of configsList) {
    await updateConfigTrafficFromPanel(config);
    const nowMs = Date.now();
    const isExpired = config.expiryTime && config.expiryTime < nowMs && !config.isUnlimitedTime;
    const usedGb = config.usedTrafficBytes ? config.usedTrafficBytes / 1024 ** 3 : 0;
    const isFull = config.volumeGb && usedGb >= config.volumeGb && !config.isUnlimitedVolume;
    if (isExpired || isFull) {
      if (config.isActive) await updateConfig(config.id, { isActive: false });
      continue;
    }
    hasActive = true;
    const statusIcon = config.isTest ? '🧪' : '✅';
    const typeLabel = config.isTest ? 'تست' : 'خریداری شده';
    const remaining = (config.expiryTime && !config.isUnlimitedTime) ? formatRemainingTime(config.expiryTime) : '♾️ نامحدود';
    text += `${statusIcon} **${config.username}** (${typeLabel})\n└ ${remaining}\n`;
    kbButtons.push([{ text: `${statusIcon} ${config.username}`, callback_data: `service_detail:${config.id}` }]);
  }

  if (!hasActive) {
    return api.sendMessage({
      chat_id: chatId,
      text: '📦 **سرویس‌های شما:**\n⚠️ در حال حاضر سرویس فعالی ندارید.\n_(سرویس‌های منقضی شده در این لیست نمایش داده نمی‌شوند)_',
      parse_mode: 'Markdown',
    });
  }
  kbButtons.push([{ text: '🔄 بروزرسانی', callback_data: 'services_refresh' }]);
  await api.sendMessage({ chat_id: chatId, text, reply_markup: { inline_keyboard: kbButtons }, parse_mode: 'Markdown' });
}

export async function refreshServices(callback) {
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: '🔄 در حال بروزرسانی...' });
  const configsList = await listConfigsByUser(callback.from.id);
  for (const config of configsList) await updateConfigTrafficFromPanel(config);
  try { await api.deleteMessage({ chat_id: callback.message.chat.id, message_id: callback.message.message_id }); } catch { /* ignore */ }
  await myServicesMenu(callback.message.chat.id, callback.from.id);
}

export async function serviceDetail(callback) {
  const configId = parseInt(callback.data.split(':')[1], 10);
  const config = await getConfigByIdForUser(configId, callback.from.id);
  if (!config) return api.answerCallbackQuery({ callback_query_id: callback.id, text: '❌ یافت نشد', show_alert: true });
  const res = await updateConfigTrafficFromPanel(config);

  let usageInfo;
  if (res && res.success) {
    const usedBytes = res.used || 0;
    const totalBytes = res.total || 0;
    const usedStr = formatBytes(usedBytes);
    if (totalBytes > 0) {
      const percent = (usedBytes / totalBytes) * 100;
      const filled = Math.floor((percent / 100) * 10);
      const progress = '█'.repeat(filled) + '░'.repeat(10 - filled);
      usageInfo = `${progress} ${percent.toFixed(1)}%\n📊 \`${usedStr}\` از \`${formatBytes(totalBytes)}\``;
    } else {
      usageInfo = `♾️ **نامحدود**\n📊 مصرف: \`${usedStr}\``;
    }
  } else {
    const usedBytes = config.usedTrafficBytes || 0;
    const usedStr = formatBytes(usedBytes);
    if (config.isUnlimitedVolume || config.volumeGb <= 0) usageInfo = `♾️ **نامحدود**\n📊 مصرف: \`${usedStr}\``;
    else usageInfo = `📊 \`${usedStr}\` از \`${config.volumeGb} GB\``;
  }

  let statusText;
  if (config.isTest) statusText = '🧪 **تست**';
  else if (config.isActive) statusText = '✅ **فعال**';
  else statusText = '⛔ **منقضی**';

  const remaining = !config.isUnlimitedTime ? formatRemainingTime(config.expiryTime) : '♾️ نامحدود';
  const inboundsCount = config.inboundIds ? config.inboundIds.split(',').length : '?';
  const durationDisplay = (config.isUnlimitedTime || config.durationDays <= 0) ? '♾️ نامحدود' : `\`${config.durationDays} روز\``;
  const volumeDisplay = (config.isUnlimitedVolume || config.volumeGb <= 0) ? '♾️ نامحدود' : `\`${config.volumeGb} GB\``;

  const text = '📦 **جزئیات سرویس**\n' +
    `🆔 \`${config.username}\`\n` +
    `📊 ${statusText}\n` +
    `📈 **حجم:**\n${usageInfo}\n` +
    `⏳ **زمان:**\n${remaining}\n` +
    `📦 حجم: ${volumeDisplay}\n` +
    `📅 مدت: ${durationDisplay}\n` +
    `🎯 \`${inboundsCount}\` اینباند\n` +
    `🔗 **لینک:**\n<code>${config.subLink}</code>`;

  const kbButtons = [[{ text: '📋 کپی لینک', callback_data: `copy_sub:${config.id}` }]];
  if (!config.isActive && !config.isTest) kbButtons.push([{ text: '🔄 تمدید', callback_data: `renew_service:${config.id}` }]);
  kbButtons.push([{ text: '🔙 بازگشت', callback_data: 'back_to_services' }]);

  try {
    await api.editMessageText({ chat_id: callback.message.chat.id, message_id: callback.message.message_id, text, reply_markup: { inline_keyboard: kbButtons }, parse_mode: 'HTML' });
  } catch {
    await api.sendMessage({ chat_id: callback.message.chat.id, text, reply_markup: { inline_keyboard: kbButtons }, parse_mode: 'HTML' });
  }
}

export async function backToServices(callback) {
  try { await api.deleteMessage({ chat_id: callback.message.chat.id, message_id: callback.message.message_id }); } catch { /* ignore */ }
  await myServicesMenu(callback.message.chat.id, callback.from.id);
}

export async function copySubLink(callback) {
  const configId = parseInt(callback.data.split(':')[1], 10);
  const config = await getConfigByIdForUser(configId, callback.from.id);
  if (config) {
    await api.sendMessage({ chat_id: callback.message.chat.id, text: `🔗 **${config.username}:**\n<code>${config.subLink}</code>`, parse_mode: 'HTML' });
    await api.answerCallbackQuery({ callback_query_id: callback.id, text: '✅ ارسال شد' });
  } else {
    await api.answerCallbackQuery({ callback_query_id: callback.id, text: '❌ یافت نشد', show_alert: true });
  }
}

export async function renewServiceRedirect(callback) {
  await api.answerCallbackQuery({ callback_query_id: callback.id, text: 'از بخش «🔄 تمدید» استفاده کنید.', show_alert: true });
}
