// Port of bot/panel_api.py (3x-ui / s-ui style panel REST API) to sdk/fetch.
// There is no persistent aiohttp.ClientSession here — each call just issues
// a fresh HTTP request with the server's Bearer token; that's fine, the
// handler invocation itself is already short-lived.
import { fetch } from 'sdk';
import { db } from 'sdk';
import { eq, asc } from 'sdk/db';
import { servers } from '../schema.js';
import { getSetting, getSelectedInboundIds } from './db/settings.js';
import { uuidv4, randomHex } from './helpers.js';

async function getBestServer() {
  const rows = await db.select().from(servers).where(eq(servers.isActive, true)).orderBy(asc(servers.priority)).all();
  return rows[0] || null;
}

async function getServerById(id) {
  if (id == null) return null;
  return await db.select().from(servers).where(eq(servers.id, id)).get();
}

async function resolveServer(serverId) {
  return serverId ? await getServerById(serverId) : await getBestServer();
}

function authHeaders(server) {
  return {
    Authorization: `Bearer ${server.apiKey}`,
    Accept: 'application/json',
    'Content-Type': 'application/json',
  };
}

async function safeJson(res) {
  try { return await res.json(); } catch { return null; }
}

export async function getInboundOptions(serverId = null) {
  const server = await resolveServer(serverId);
  if (!server) return { success: false, msg: '❌ سروری تنظیم نشده.', inbounds: [] };
  try {
    const res = await fetch(`${server.url.replace(/\/$/, '')}/panel/api/inbounds/options`, { headers: authHeaders(server) });
    if (res.status === 200) {
      const data = await safeJson(res);
      const inbounds = data && typeof data === 'object' ? (data.obj ?? data) : data;
      return { success: true, inbounds: Array.isArray(inbounds) ? inbounds : [], server };
    }
    if (res.status === 401) return { success: false, msg: '❌ API Token نامعتبر.', inbounds: [] };
    return { success: false, msg: `HTTP ${res.status}`, inbounds: [] };
  } catch (e) {
    return { success: false, msg: `خطای اتصال: ${e.message || e}`, inbounds: [] };
  }
}

export async function getNewUuid(serverId = null) {
  const server = await resolveServer(serverId);
  const fallback = () => uuidv4();
  if (!server) return fallback();
  try {
    const res = await fetch(`${server.url.replace(/\/$/, '')}/panel/api/server/getNewUUID`, { headers: authHeaders(server) });
    if (res.status === 200) {
      const data = await safeJson(res);
      if (typeof data === 'string') return data;
      if (data && typeof data === 'object') {
        const obj = data.obj;
        if (typeof obj === 'string' && obj) return obj;
        if (obj && typeof obj === 'object') {
          for (const key of ['id', 'uuid', 'UUID', 'Id']) if (typeof obj[key] === 'string') return obj[key];
        }
        for (const key of ['uuid', 'id', 'UUID']) if (typeof data[key] === 'string') return data[key];
      }
    }
  } catch { /* fall through to random uuid */ }
  return fallback();
}

export async function getServerStatus(serverId = null) {
  const server = await resolveServer(serverId);
  if (!server) return { success: false, msg: '❌ سرور یافت نشد' };
  try {
    const res = await fetch(`${server.url.replace(/\/$/, '')}/panel/api/server/status`, { headers: authHeaders(server) });
    if (res.status === 200) {
      const data = await safeJson(res);
      const obj = data && typeof data === 'object' ? (data.obj ?? data) : {};
      return {
        success: true, server,
        cpu: obj.cpu || 0,
        memCurrent: obj.mem?.current || 0, memTotal: obj.mem?.total || 1,
        swapCurrent: obj.swap?.current || 0, swapTotal: obj.swap?.total || 1,
        disk: obj.disk || [], netIO: obj.netIO || {}, loads: obj.loads || [0, 0, 0],
        tcpCount: obj.tcpCount || 0, udpCount: obj.udpCount || 0,
        xrayState: obj.xray?.state || 'unknown', appUptime: obj.appStats?.uptime || 0,
      };
    }
    return { success: false, msg: `HTTP ${res.status}` };
  } catch (e) {
    return { success: false, msg: String(e.message || e) };
  }
}

export async function getClientGroups(serverId = null) {
  const server = await resolveServer(serverId);
  if (!server) return { success: false, msg: '❌ سرور یافت نشد' };
  try {
    const res = await fetch(`${server.url.replace(/\/$/, '')}/panel/api/clients/groups`, { headers: authHeaders(server) });
    if (res.status === 200) {
      const data = await safeJson(res);
      const groups = data && typeof data === 'object' ? (data.obj ?? data) : data;
      return { success: true, groups: Array.isArray(groups) ? groups : [] };
    }
    return { success: false, msg: `HTTP ${res.status}` };
  } catch (e) {
    return { success: false, msg: String(e.message || e) };
  }
}

export async function getSubBaseUrl(server) {
  const customPattern = (await getSetting('sub_link_pattern', '')).trim();
  if (customPattern) {
    const base = customPattern.replace(/\/?\{sub_?[Ii][Dd]\}\/?$/, '');
    return base.replace(/\/$/, '');
  }
  try {
    const res = await fetch(`${server.url.replace(/\/$/, '')}/panel/api/setting/all`, { method: 'POST', headers: authHeaders(server) });
    if (res.status === 200) {
      let data = await safeJson(res);
      let obj = data && typeof data === 'object' ? (data.obj ?? data) : {};
      if (typeof obj === 'string') { try { obj = JSON.parse(obj); } catch { obj = {}; } }
      const subBaseUri = obj.subBaseUri || obj.subURI || '';
      if (subBaseUri && subBaseUri.startsWith('http')) return subBaseUri.replace(/\/$/, '');
      const subPath = (obj.subPath || 'sub').replace(/^\/|\/$/g, '');
      const subPort = String(obj.subPort || '').trim();
      const subDomain = (obj.subDomain || '').trim();
      const parsedPanel = new URL(server.url);
      const protocol = parsedPanel.protocol.replace(':', '') || 'https';
      const panelHost = parsedPanel.hostname || 'localhost';
      if (subDomain) {
        if (subDomain.startsWith('http')) {
          const hostPart = new URL(subDomain).host || subDomain;
          return `${protocol}://${hostPart}/${subPath}`;
        }
        return `${protocol}://${subDomain}/${subPath}`;
      }
      if (subPort) return `${protocol}://${panelHost}:${subPort}/${subPath}`;
      return `${server.url.replace(/\/$/, '')}/${subPath}`;
    }
  } catch { /* fall through to default */ }
  return `${server.url.replace(/\/$/, '')}/sub`;
}

export async function getSubLink(subId, server) {
  const customPattern = (await getSetting('sub_link_pattern', '')).trim();
  if (customPattern) {
    return customPattern
      .replaceAll('{subId}', subId).replaceAll('{sub_id}', subId)
      .replaceAll('{SubId}', subId).replaceAll('{SUB_ID}', subId).replaceAll('{subID}', subId);
  }
  const base = await getSubBaseUrl(server);
  return `${base.replace(/\/$/, '')}/${subId}`;
}

export async function getClientTraffic(email, serverId = null) {
  const server = await resolveServer(serverId);
  if (!server) return { success: false, msg: 'سرور یافت نشد' };
  try {
    const res = await fetch(`${server.url.replace(/\/$/, '')}/panel/api/clients/traffic/${encodeURIComponent(email)}`, { headers: authHeaders(server) });
    if (res.status === 200) {
      const data = await safeJson(res);
      const obj = data ? data.obj ?? data : null;
      if (obj) {
        const up = obj.up || 0, down = obj.down || 0;
        return { success: true, up, down, used: up + down, total: obj.total || 0, expiryTime: obj.expiryTime || 0, enable: obj.enable !== false };
      }
      return { success: false, msg: 'کاربر یافت نشد' };
    }
    return { success: false, msg: `HTTP ${res.status}` };
  } catch (e) {
    return { success: false, msg: String(e.message || e) };
  }
}

export async function addClient({
  email, totalGb, expiryHours, serverId = null, inboundIds = null,
  flow = 'xtls-rprx-vision', unlimitedVolume = false, unlimitedTime = false, groupName = null,
}) {
  const server = await resolveServer(serverId);
  if (!server) return { success: false, msg: '❌ سرور فعالی تنظیم نشده.' };
  let ids = inboundIds;
  if (!ids || !ids.length) {
    // Fall back to the admin-selected inbounds (lib/admin/inbounds.js) before
    // defaulting to "every inbound the panel reports".
    ids = await getSelectedInboundIds();
  }
  if (!ids || !ids.length) {
    const res = await getInboundOptions(server.id);
    if (!res.success) return res;
    ids = res.inbounds.map((ib) => ib.id);
    if (!ids.length) return { success: false, msg: 'هیچ اینباندی یافت نشد' };
  }
  const clientUuid = (await getNewUuid(server.id)) || uuidv4();
  const subId = randomHex(16);
  const expiryTimeMs = (unlimitedTime || expiryHours <= 0) ? 0 : Date.now() + expiryHours * 3600 * 1000;
  const totalBytes = (unlimitedVolume || totalGb <= 0) ? 0 : Math.round(totalGb * 1024 * 1024 * 1024);
  const clientData = {
    email, enable: true, limitIp: 0, totalGB: totalBytes,
    expiryTime: expiryTimeMs, subId, flow, id: clientUuid,
  };
  if (groupName) clientData.group_name = groupName;
  try {
    const res = await fetch(`${server.url.replace(/\/$/, '')}/panel/api/clients/add`, {
      method: 'POST', headers: authHeaders(server),
      body: fetch.body.json({ client: clientData, inboundIds: ids }),
    });
    const result = await safeJson(res);
    if (result && result.success) {
      const subLink = await getSubLink(subId, server);
      return {
        success: true, subLink, subId, email, uuid: clientUuid, expiryTimeMs,
        serverId: server.id, serverName: server.name, inboundIds: ids, inboundsCount: ids.length,
      };
    }
    return { success: false, msg: (result && result.msg) || 'خطای ناشناخته', obj: result && result.obj };
  } catch (e) {
    return { success: false, msg: `خطای اتصال: ${e.message || e}` };
  }
}

export async function renewClient({
  email, totalGb, expiryHours, serverId = null, unlimitedVolume = false, unlimitedTime = false,
}) {
  const server = await resolveServer(serverId);
  if (!server) return { success: false, msg: 'سرور یافت نشد' };
  const addDays = (unlimitedTime || expiryHours <= 0) ? 365 * 100 : Math.floor(expiryHours / 24);
  const addBytes = (unlimitedVolume || totalGb <= 0) ? 1024 * 1024 * 1024 * 1024 * 100 : Math.round(totalGb * 1024 * 1024 * 1024);
  try {
    const res = await fetch(`${server.url.replace(/\/$/, '')}/panel/api/clients/bulkAdjust`, {
      method: 'POST', headers: authHeaders(server),
      body: fetch.body.json({ emails: [email], addDays, addBytes, reset: false }),
    });
    const result = await safeJson(res);
    if (result && result.success) {
      const newExpiry = unlimitedTime ? 0 : Date.now() + expiryHours * 3600 * 1000;
      return { success: true, expiryTimeMs: newExpiry, serverId: server.id };
    }
    return { success: false, msg: (result && result.msg) || 'خطا' };
  } catch (e) {
    return { success: false, msg: String(e.message || e) };
  }
}

export async function testServerConnection(url, apiKey) {
  try {
    const res = await fetch(`${url.replace(/\/$/, '')}/panel/api/inbounds/options`, {
      headers: { Authorization: `Bearer ${apiKey}`, Accept: 'application/json' },
    });
    if (res.status === 200) {
      const data = await safeJson(res);
      const inbounds = data && typeof data === 'object' ? (data.obj ?? data) : data;
      return { success: true, count: Array.isArray(inbounds) ? inbounds.length : 0 };
    }
    if (res.status === 401) return { success: false, msg: 'Token نامعتبر.' };
    return { success: false, msg: `HTTP ${res.status}` };
  } catch (e) {
    return { success: false, msg: String(e.message || e) };
  }
}

export { getBestServer, getServerById };
