import aiohttp, json, time, uuid as uuid_lib, re, logging
from urllib.parse import urlparse
from sqlalchemy import select
from bot.database import get_db, get_cfg, Server

class MultiServerPanelAPI:
    def __init__(self):
        self.sessions = {}

    async def _get_session(self, server):
        if server.id not in self.sessions or self.sessions[server.id].closed:
            self.sessions[server.id] = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {server.api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        return self.sessions[server.id], server.url.rstrip('/')

    async def get_best_server(self):
        async for session in get_db():
            result = await session.execute(
                select(Server).where(Server.is_active == True).order_by(Server.priority.asc())
            )
            return result.scalars().first()
        return None

    async def get_server_by_id(self, server_id):
        async for session in get_db():
            result = await session.execute(select(Server).where(Server.id == server_id))
            return result.scalar_one_or_none()

    async def get_inbound_options(self, server_id: int = None):
        server = await self.get_server_by_id(server_id) if server_id else await self.get_best_server()
        if not server: return {"success": False, "msg": "❌ سروری تنظیم نشده.", "inbounds": []}
        session, base_url = await self._get_session(server)
        try:
            async with session.get(f"{base_url}/panel/api/inbounds/options", timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    inbounds = data.get("obj", data) if isinstance(data, dict) else data
                    return {"success": True, "inbounds": inbounds, "server": server}
                if resp.status == 401: return {"success": False, "msg": "❌ API Token نامعتبر.", "inbounds": []}
                return {"success": False, "msg": f"HTTP {resp.status}", "inbounds": []}
        except aiohttp.ClientConnectorError: return {"success": False, "msg": "❌ سرور قابل دسترسی نیست.", "inbounds": []}
        except Exception as e: return {"success": False, "msg": f"خطای اتصال: {str(e)}", "inbounds": []}

    async def get_new_uuid(self, server_id: int = None):
        server = await self.get_server_by_id(server_id) if server_id else await self.get_best_server()
        if not server: return str(uuid_lib.uuid4())
        session, base_url = await self._get_session(server)
        try:
            async with session.get(f"{base_url}/panel/api/server/getNewUUID", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, str): return data
                    if isinstance(data, dict):
                        obj = data.get("obj")
                        if isinstance(obj, str) and obj: return obj
                        if isinstance(obj, dict):
                            for key in ["id", "uuid", "UUID", "Id"]:
                                if key in obj and isinstance(obj[key], str): return obj[key]
                        for key in ["uuid", "id", "UUID"]:
                            if key in data and isinstance(data[key], str): return data[key]
        except Exception as e: logging.error(f"get_new_uuid error: {e}")
        return str(uuid_lib.uuid4())

    async def get_server_status(self, server_id: int = None) -> dict:
        server = await self.get_server_by_id(server_id) if server_id else await self.get_best_server()
        if not server: return {"success": False, "msg": "❌ سرور یافت نشد"}
        session, base_url = await self._get_session(server)
        try:
            async with session.get(f"{base_url}/panel/api/server/status", timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    obj = data.get("obj", data) if isinstance(data, dict) else data
                    return {
                        "success": True, "server": server,
                        "cpu": obj.get("cpu", 0), "mem_current": obj.get("mem", {}).get("current", 0),
                        "mem_total": obj.get("mem", {}).get("total", 1), "swap_current": obj.get("swap", {}).get("current", 0),
                        "swap_total": obj.get("swap", {}).get("total", 1), "disk": obj.get("disk", []),
                        "net_io": obj.get("netIO", {}), "loads": obj.get("loads", [0, 0, 0]),
                        "tcp_count": obj.get("tcpCount", 0), "udp_count": obj.get("udpCount", 0),
                        "xray_state": obj.get("xray", {}).get("state", "unknown"), "app_uptime": obj.get("appStats", {}).get("uptime", 0),
                    }
                return {"success": False, "msg": f"HTTP {resp.status}"}
        except Exception as e: return {"success": False, "msg": str(e)}

    async def get_client_groups(self, server_id: int = None) -> dict:
        server = await self.get_server_by_id(server_id) if server_id else await self.get_best_server()
        if not server: return {"success": False, "msg": "❌ سرور یافت نشد"}
        session, base_url = await self._get_session(server)
        try:
            async with session.get(f"{base_url}/panel/api/clients/groups", timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    groups = data.get("obj", data) if isinstance(data, dict) else data
                    return {"success": True, "groups": groups if isinstance(groups, list) else []}
                return {"success": False, "msg": f"HTTP {resp.status}"}
        except Exception as e: return {"success": False, "msg": str(e)}

    async def get_sub_base_url(self, server) -> str:
        custom_pattern = await get_cfg("sub_link_pattern", "")
        if custom_pattern and custom_pattern.strip():
            base = re.sub(r'/?\{sub_?[Ii][Dd]\}/?$', '', custom_pattern.strip(), flags=re.IGNORECASE)
            return base.rstrip('/')
        session, base_url = await self._get_session(server)
        try:
            async with session.post(f"{base_url}/panel/api/setting/all", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    obj = data.get("obj", data) if isinstance(data, dict) else {}
                    if isinstance(obj, str):
                        try: obj = json.loads(obj)
                        except: obj = {}
                    sub_base_uri = obj.get("subBaseUri", "") or obj.get("subURI", "")
                    if sub_base_uri and sub_base_uri.startswith("http"): return sub_base_uri.rstrip('/')
                    sub_path = (obj.get("subPath", "sub") or "sub").strip('/')
                    sub_port = str(obj.get("subPort", "") or "").strip()
                    sub_domain = (obj.get("subDomain", "") or "").strip()
                    parsed_panel = urlparse(base_url)
                    protocol = parsed_panel.scheme or "https"
                    panel_host = parsed_panel.hostname or "localhost"
                    if sub_domain:
                        if sub_domain.startswith("http"):
                            host_part = urlparse(sub_domain).netloc or sub_domain
                            return f"{protocol}://{host_part}/{sub_path}"
                        return f"{protocol}://{sub_domain}/{sub_path}"
                    if sub_port: return f"{protocol}://{panel_host}:{sub_port}/{sub_path}"
                    return f"{base_url}/{sub_path}"
        except Exception: pass
        return f"{server.url.rstrip('/')}/sub"

    async def get_sub_link(self, sub_id: str, server) -> str:
        custom_pattern = await get_cfg("sub_link_pattern", "")
        if custom_pattern and custom_pattern.strip():
            return (custom_pattern.replace("{subId}", sub_id).replace("{sub_id}", sub_id)
                    .replace("{SubId}", sub_id).replace("{SUB_ID}", sub_id).replace("{subID}", sub_id))
        base = await self.get_sub_base_url(server)
        return f"{base.rstrip('/')}/{sub_id}"

    async def get_client_traffic(self, email: str, server_id: int = None) -> dict:
        server = await self.get_server_by_id(server_id) if server_id else await self.get_best_server()
        if not server: return {"success": False, "msg": "سرور یافت نشد"}
        session, base_url = await self._get_session(server)
        try:
            async with session.get(f"{base_url}/panel/api/clients/traffic/{email}", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    obj = data.get("obj", data)
                    if obj:
                        up = obj.get("up", 0) or 0
                        down = obj.get("down", 0) or 0
                        total = obj.get("total", 0) or 0
                        return {"success": True, "up": up, "down": down, "used": up + down, "total": total,
                                "expiryTime": obj.get("expiryTime", 0), "enable": obj.get("enable", True)}
                    return {"success": False, "msg": "کاربر یافت نشد"}
        except Exception as e: return {"success": False, "msg": str(e)}

    async def add_client(self, email: str, total_gb: float, expiry_hours: int, server_id: int = None, 
                         inbound_ids: list = None, flow: str = "xtls-rprx-vision",
                         unlimited_volume: bool = False, unlimited_time: bool = False, group_name: str = None) -> dict:
        server = await self.get_server_by_id(server_id) if server_id else await self.get_best_server()
        if not server: return {"success": False, "msg": "❌ سرور فعالی تنظیم نشده."}
        if not inbound_ids:
            inbounds_res = await self.get_inbound_options(server.id)
            if not inbounds_res["success"]: return inbounds_res
            inbound_ids = [ib["id"] for ib in inbounds_res["inbounds"]]
            if not inbound_ids: return {"success": False, "msg": "هیچ اینباندی یافت نشد"}
        
        client_uuid = await self.get_new_uuid(server.id)
        if not isinstance(client_uuid, str): client_uuid = str(uuid_lib.uuid4())
        sub_id = uuid_lib.uuid4().hex[:16]
        
        expiry_time_ms = 0 if unlimited_time or expiry_hours <= 0 else int(time.time() * 1000) + (expiry_hours * 3600 * 1000)
        total_bytes = 0 if unlimited_volume or total_gb <= 0 else int(total_gb * 1024 * 1024 * 1024)
        
        client_data = {
            "email": email, "enable": True, "limitIp": 0, "totalGB": total_bytes, 
            "expiryTime": expiry_time_ms, "subId": sub_id, "flow": flow, "id": client_uuid,
        }
        if group_name: client_data["group_name"] = group_name
        payload = {"client": client_data, "inboundIds": inbound_ids}
        
        session, base_url = await self._get_session(server)
        try:
            async with session.post(f"{base_url}/panel/api/clients/add", json=payload, timeout=20) as resp:
                result = await resp.json()
                if result.get("success"):
                    sub_link = await self.get_sub_link(sub_id, server)
                    return {"success": True, "sub_link": sub_link, "sub_id": sub_id, "email": email, 
                            "uuid": client_uuid, "expiry_time_ms": expiry_time_ms, "server_id": server.id, 
                            "server_name": server.name, "inbound_ids": inbound_ids, "inbounds_count": len(inbound_ids)}
                return {"success": False, "msg": result.get("msg", "خطای ناشناخته"), "obj": result.get("obj")}
        except Exception as e: return {"success": False, "msg": f"خطای اتصال: {str(e)}"}

    async def renew_client(self, email: str, total_gb: float, expiry_hours: int, server_id: int = None,
                         unlimited_volume: bool = False, unlimited_time: bool = False) -> dict:
        server = await self.get_server_by_id(server_id) if server_id else await self.get_best_server()
        if not server: return {"success": False, "msg": "سرور یافت نشد"}
        session, base_url = await self._get_session(server)
        add_days = 365 * 100 if unlimited_time or expiry_hours <= 0 else expiry_hours // 24
        add_bytes = 1024 * 1024 * 1024 * 1024 * 100 if unlimited_volume or total_gb <= 0 else int(total_gb * 1024 * 1024 * 1024)
        payload = {"emails": [email], "addDays": add_days, "addBytes": add_bytes, "reset": False}
        try:
            async with session.post(f"{base_url}/panel/api/clients/bulkAdjust", json=payload, timeout=15) as resp:
                result = await resp.json()
                if result.get("success"):
                    new_expiry = int(time.time() * 1000) + (expiry_hours * 3600 * 1000) if not unlimited_time else 0
                    return {"success": True, "expiry_time_ms": new_expiry, "server_id": server.id}
                return {"success": False, "msg": result.get("msg", "خطا")}
        except Exception as e: return {"success": False, "msg": str(e)}

    async def close(self):
        for s in self.sessions.values():
            if not s.closed: await s.close()

panel_api = MultiServerPanelAPI()
