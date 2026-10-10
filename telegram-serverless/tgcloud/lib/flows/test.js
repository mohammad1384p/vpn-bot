// Port of bot/handlers/test.py
import { api } from 'sdk';
import { getUserByTelegramId } from '../db/users.js';
import { createConfig, countActiveTestConfigs } from '../db/configs.js';
import { getSetting, getSelectedInboundIds } from '../db/settings.js';
import { addClient } from '../panel.js';
import { requiresPhoneAuth } from './start.js';
import { PHONE_KB } from '../keyboards.js';
import { sendConfigPackage } from '../sendConfig.js';

export async function getTestAccount(message) {
  const chatId = message.chat.id;
  const telegramId = message.from.id;
  try { await api.sendChatAction({ chat_id: chatId, action: 'typing' }); } catch { /* ignore */ }

  const user = await getUserByTelegramId(telegramId);
  if (!user) return api.sendMessage({ chat_id: chatId, text: '⚠️ لطفاً ابتدا /start را بزنید.' });
  if (requiresPhoneAuth(user)) {
    return api.sendMessage({ chat_id: chatId, text: '🔐 چون با لینک زیرمجموعه وارد شده‌اید، برای دریافت اکانت تست ابتدا شماره تماس خود را تایید کنید.', reply_markup: PHONE_KB });
  }

  const cooldownHours = parseInt(await getSetting('test_cooldown_hours', '24'), 10);
  const maxTest = parseInt(await getSetting('max_test_per_user', '1'), 10);
  const volumeMb = parseInt(await getSetting('test_volume_mb', '100'), 10);
  const durationHours = parseInt(await getSetting('test_duration_hours', '1'), 10);

  if (user.lastTestTime) {
    const lastMs = user.lastTestTime instanceof Date ? user.lastTestTime.getTime() : user.lastTestTime;
    const elapsedHours = (Date.now() - lastMs) / 3600000;
    if (elapsedHours < cooldownHours) {
      const remaining = (cooldownHours - elapsedHours).toFixed(1);
      return api.sendMessage({ chat_id: chatId, text: `⏳ **${remaining} ساعت صبر کنید.**`, parse_mode: 'Markdown' });
    }
  }

  const testCount = await countActiveTestConfigs(telegramId);
  if (testCount >= maxTest) {
    return api.sendMessage({ chat_id: chatId, text: `⚠️ **محدودیت تست**\nحداکثر \`${maxTest}\` اکانت تست فعال.\n📊 فعلی: \`${testCount}\``, parse_mode: 'Markdown' });
  }

  const email = `test_${telegramId}_${Math.floor(Date.now() / 1000)}`;
  const selectedIds = await getSelectedInboundIds();
  const res = await addClient({
    email, totalGb: volumeMb / 1024, expiryHours: durationHours,
    inboundIds: selectedIds.length ? selectedIds : null,
  });

  if (res.success) {
    const { updateUser } = await import('../db/users.js');
    await updateUser(telegramId, { lastTestTime: new Date() });
    const inboundIdsStr = (res.inboundIds || []).join(',');
    await createConfig({
      telegramId, username: email, subLink: res.subLink, subId: res.subId || null,
      isActive: true, expiryTime: res.expiryTimeMs, volumeGb: Math.max(1, Math.floor(volumeMb / 1024)),
      durationDays: 1, inboundIds: inboundIdsStr, isTest: true,
    });
    await sendConfigPackage({
      userId: telegramId, subLink: res.subLink, username: email,
      volumeDisplay: `${volumeMb} MB`, durationDisplay: `${durationHours} ساعت`, isTest: true,
    });
  } else {
    await api.sendMessage({ chat_id: chatId, text: `❌ خطا: ${res.msg}` });
  }
}
