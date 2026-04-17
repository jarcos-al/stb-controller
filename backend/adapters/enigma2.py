"""
Enigma2 STB Adapter using OpenWebif API.
Communicates via HTTP REST to the STB's OpenWebif plugin.
"""

import httpx
from typing import Optional
from datetime import datetime

from backend.adapters.base import STBAdapter
from backend.models.schemas import (
    STBStatus,
    KeyPressResponse,
    Channel,
    Bouquet,
    ZapResponse,
    EPGEvent,
    EPGNowNext,
    Timer,
    TimerResponse,
    VolumeState,
    DiscoveredDevice,
)
from backend.core.logging import get_logger

log = get_logger("enigma2_adapter")


# Enigma2 Remote Control keycodes
E2_KEYCODES = {
    "POWER": 116, "OK": 352, "ENTER": 352,
    "UP": 103, "DOWN": 108, "LEFT": 105, "RIGHT": 106,
    "MENU": 139, "EXIT": 174, "BACK": 174,
    "VOL_UP": 115, "VOL_DOWN": 114, "MUTE": 113,
    "CH_UP": 402, "CH_DOWN": 403,
    "EPG": 358, "INFO": 358,
    "RED": 398, "GREEN": 399, "YELLOW": 400, "BLUE": 401,
    "0": 11, "1": 2, "2": 3, "3": 4, "4": 5,
    "5": 6, "6": 7, "7": 8, "8": 9, "9": 10,
    "PLAY": 207, "PAUSE": 119, "STOP": 128,
    "REC": 167, "FF": 208, "REW": 168,
    "BOUQUET_UP": 402, "BOUQUET_DOWN": 403,
    "TV": 377, "RADIO": 385,
    "TEXT": 388, "SUBTITLE": 370, "AUDIO": 392,
}


class Enigma2Adapter(STBAdapter):
    """
    Adapter for Enigma2 set-top boxes via OpenWebif HTTP API.

    Supports: Vu+, Zgemma, Gigablue, DreamBox and any Enigma2-based STB
    with the OpenWebif plugin installed.
    """

    def __init__(self, host: str, port: int = 80, credentials: dict = None, options: dict = None):
        super().__init__(host, port, credentials, options)
        self._base_url = f"http://{host}:{port}"
        self._streaming_port = (options or {}).get("streaming_port", 8001)
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client with auth if needed."""
        if self._client is None or self._client.is_closed:
            auth = None
            if self.credentials.get("username"):
                auth = httpx.BasicAuth(
                    self.credentials["username"],
                    self.credentials.get("password", ""),
                )
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                auth=auth,
                timeout=10.0,
            )
        return self._client

    async def _api_get(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to the OpenWebif JSON API."""
        client = self._get_client()
        try:
            url = f"/api/{endpoint}"
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            log.error("enigma2_api_error", endpoint=endpoint, status=e.response.status_code)
            raise
        except httpx.ConnectError:
            log.error("enigma2_connection_failed", host=self.host)
            self._connected = False
            raise
        except Exception as e:
            log.error("enigma2_request_failed", endpoint=endpoint, error=str(e))
            raise

    # ──── Connection ────

    async def connect(self) -> bool:
        try:
            data = await self._api_get("about")
            info = data.get("info", {})
            log.info("enigma2_connected",
                     model=info.get("model", "Unknown"),
                     image=info.get("imagedistro", "Unknown"))
            self._connected = True
            return True
        except Exception as e:
            log.error("enigma2_connect_failed", error=str(e))
            self._connected = False
            return False

    async def disconnect(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._connected = False

    async def check_health(self) -> bool:
        try:
            data = await self._api_get("statusinfo")
            return True
        except Exception:
            self._connected = False
            return False

    # ──── Status ────

    async def get_status(self) -> STBStatus:
        try:
            data = await self._api_get("statusinfo")
            about = await self._api_get("about")
            info = about.get("info", {})

            return STBStatus(
                in_standby=data.get("inStandby") == "true",
                current_channel=data.get("currservice_station", ""),
                current_channel_ref=data.get("currservice_serviceref", ""),
                current_program=data.get("currservice_name", ""),
                program_description=data.get("currservice_fulldescription", ""),
                program_start=data.get("currservice_begin"),
                program_end=data.get("currservice_end"),
                volume=data.get("volume", 0),
                is_muted=data.get("muted", False),
                is_recording=data.get("isRecording") == "true",
                device_name=info.get("brand", "") + " " + info.get("model", ""),
                device_model=info.get("model", ""),
            )
        except Exception as e:
            log.error("enigma2_status_failed", error=str(e))
            return STBStatus(device_name="Enigma2 (offline)")

    # ──── Remote Control ────

    async def send_key(self, key: str, key_type: str = "short") -> KeyPressResponse:
        key_upper = key.upper()
        if key_upper not in E2_KEYCODES:
            return KeyPressResponse(result=False, message=f"Unknown key: {key}")

        command = E2_KEYCODES[key_upper]
        params = {"command": command}
        if key_type == "long":
            params["type"] = "long"

        try:
            data = await self._api_get("remotecontrol", params)
            return KeyPressResponse(
                result=data.get("result", False),
                message=data.get("message", ""),
            )
        except Exception as e:
            return KeyPressResponse(result=False, message=str(e))

    # ──── Channels ────

    async def get_bouquets(self) -> list[Bouquet]:
        try:
            data = await self._api_get("bouquets")
            bouquets = []
            for i, svc in enumerate(data.get("bouquets", [])):
                bouquets.append(Bouquet(
                    id=i + 1,
                    name=svc.get("servicename", ""),
                    service_ref=svc.get("servicereference", ""),
                ))
            return bouquets
        except Exception as e:
            log.error("enigma2_bouquets_failed", error=str(e))
            return []

    async def get_channels(self, bouquet_ref: Optional[str] = None) -> list[Channel]:
        try:
            params = {}
            if bouquet_ref:
                params["sRef"] = bouquet_ref

            data = await self._api_get("getservices", params)
            channels = []
            for i, svc in enumerate(data.get("services", [])):
                sref = svc.get("servicereference", "")
                # Skip markers and separators (service ref starting with specific patterns)
                if sref.startswith("1:64:") or sref.startswith("1:832:"):
                    continue
                channels.append(Channel(
                    name=svc.get("servicename", ""),
                    service_ref=sref,
                    provider=svc.get("provider", ""),
                    is_hd="hd" in svc.get("servicename", "").lower(),
                    channel_number=i + 1,
                ))
            return channels
        except Exception as e:
            log.error("enigma2_channels_failed", error=str(e))
            return []

    async def zap(self, service_ref: str) -> ZapResponse:
        try:
            data = await self._api_get("zap", {"sRef": service_ref})
            return ZapResponse(
                result=data.get("result", False),
                message=data.get("message", ""),
            )
        except Exception as e:
            return ZapResponse(result=False, message=str(e))

    # ──── EPG ────

    async def get_epg_now_next(self, bouquet_ref: Optional[str] = None) -> list[EPGNowNext]:
        try:
            params = {}
            if bouquet_ref:
                params["bRef"] = bouquet_ref

            data = await self._api_get("epgnownext", params)
            result = []
            events = data.get("events", [])

            # Events come in pairs (now, next) per channel
            i = 0
            while i < len(events):
                now_evt = events[i]
                next_evt = events[i + 1] if i + 1 < len(events) else None

                def _parse_event(evt: dict) -> Optional[EPGEvent]:
                    if not evt or not evt.get("title"):
                        return None
                    begin = evt.get("begin_timestamp", 0)
                    duration = evt.get("duration", 0)
                    return EPGEvent(
                        event_id=evt.get("id"),
                        title=evt.get("title", ""),
                        description=evt.get("shortdesc", ""),
                        description_ext=evt.get("longdesc", ""),
                        start_time=datetime.fromtimestamp(begin).isoformat() if begin else "",
                        duration=duration,
                        service_ref=evt.get("sref", ""),
                        channel_name=evt.get("sname", ""),
                        genre=evt.get("genrename", ""),
                    )

                nn = EPGNowNext(
                    channel_name=now_evt.get("sname", ""),
                    service_ref=now_evt.get("sref", ""),
                    now=_parse_event(now_evt),
                    next=_parse_event(next_evt) if next_evt and next_evt.get("sref") == now_evt.get("sref") else None,
                )
                result.append(nn)
                i += 2 if next_evt and next_evt.get("sref") == now_evt.get("sref") else 1

            return result
        except Exception as e:
            log.error("enigma2_epg_now_next_failed", error=str(e))
            return []

    async def get_epg_service(self, service_ref: str) -> list[EPGEvent]:
        try:
            data = await self._api_get("epgservice", {"sRef": service_ref})
            events = []
            for evt in data.get("events", []):
                begin = evt.get("begin_timestamp", 0)
                events.append(EPGEvent(
                    event_id=evt.get("id"),
                    title=evt.get("title", ""),
                    description=evt.get("shortdesc", ""),
                    description_ext=evt.get("longdesc", ""),
                    start_time=datetime.fromtimestamp(begin).isoformat() if begin else "",
                    duration=evt.get("duration", 0),
                    service_ref=evt.get("sref", ""),
                    channel_name=evt.get("sname", ""),
                    genre=evt.get("genrename", ""),
                ))
            return events
        except Exception as e:
            log.error("enigma2_epg_service_failed", error=str(e))
            return []

    async def search_epg(self, query: str) -> list[EPGEvent]:
        try:
            data = await self._api_get("epgsearch", {"search": query})
            events = []
            for evt in data.get("events", []):
                begin = evt.get("begin_timestamp", 0)
                events.append(EPGEvent(
                    event_id=evt.get("id"),
                    title=evt.get("title", ""),
                    description=evt.get("shortdesc", ""),
                    description_ext=evt.get("longdesc", ""),
                    start_time=datetime.fromtimestamp(begin).isoformat() if begin else "",
                    duration=evt.get("duration", 0),
                    service_ref=evt.get("sref", ""),
                    channel_name=evt.get("sname", ""),
                ))
            return events
        except Exception as e:
            log.error("enigma2_epg_search_failed", error=str(e))
            return []

    # ──── Volume ────

    async def get_volume(self) -> VolumeState:
        try:
            data = await self._api_get("vol", {"set": "state"})
            return VolumeState(
                volume=data.get("current", 0),
                is_muted=data.get("ismute", False),
            )
        except Exception:
            return VolumeState(volume=0, is_muted=False)

    async def set_volume(self, action: str, value: Optional[int] = None) -> VolumeState:
        try:
            if action == "set" and value is not None:
                await self._api_get("vol", {"set": f"set{value}"})
            else:
                await self._api_get("vol", {"set": action})
            return await self.get_volume()
        except Exception:
            return VolumeState(volume=0, is_muted=False)

    # ──── Timers ────

    async def get_timers(self) -> list[Timer]:
        try:
            data = await self._api_get("timerlist")
            timers = []
            for t in data.get("timers", []):
                begin = t.get("begin", 0)
                end = t.get("end", 0)
                timers.append(Timer(
                    service_ref=t.get("serviceref", ""),
                    channel_name=t.get("servicename", ""),
                    begin_time=datetime.fromtimestamp(begin).isoformat() if begin else "",
                    end_time=datetime.fromtimestamp(end).isoformat() if end else "",
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    state=t.get("state", 0),
                    repeated=t.get("repeated", 0),
                ))
            return timers
        except Exception as e:
            log.error("enigma2_timers_failed", error=str(e))
            return []

    async def add_timer(self, timer: Timer) -> TimerResponse:
        try:
            begin_ts = int(datetime.fromisoformat(timer.begin_time).timestamp())
            end_ts = int(datetime.fromisoformat(timer.end_time).timestamp())

            params = {
                "sRef": timer.service_ref,
                "begin": begin_ts,
                "end": end_ts,
                "name": timer.name,
                "description": timer.description,
                "repeated": timer.repeated,
            }
            data = await self._api_get("timeradd", params)
            return TimerResponse(
                result=data.get("result", False),
                message=data.get("message", ""),
            )
        except Exception as e:
            return TimerResponse(result=False, message=str(e))

    async def delete_timer(self, service_ref: str, begin_time: str, end_time: str) -> TimerResponse:
        try:
            begin_ts = int(datetime.fromisoformat(begin_time).timestamp())
            end_ts = int(datetime.fromisoformat(end_time).timestamp())

            params = {
                "sRef": service_ref,
                "begin": begin_ts,
                "end": end_ts,
            }
            data = await self._api_get("timerdelete", params)
            return TimerResponse(
                result=data.get("result", False),
                message=data.get("message", ""),
            )
        except Exception as e:
            return TimerResponse(result=False, message=str(e))

    # ──── Power ────

    async def set_power_state(self, action: str) -> bool:
        state_map = {
            "toggle": 0,
            "deep_standby": 1,
            "reboot": 2,
            "restart": 3,
            "wakeup": 4,
            "standby": 5,
        }
        state = state_map.get(action, 0)
        try:
            await self._api_get("powerstate", {"newstate": state})
            return True
        except Exception:
            return False

    # ──── Stream ────

    async def get_stream_url(self, service_ref: str) -> Optional[str]:
        return f"http://{self.host}:{self._streaming_port}/{service_ref}"

    # ──── Discovery ────

    @staticmethod
    async def discover(network: str = "192.168.1.0/24") -> list[DiscoveredDevice]:
        """Attempt to discover Enigma2 devices on the network via HTTP probe."""
        # Simple implementation: try common IPs
        # A full implementation would use nmap or SSDP
        devices = []
        base = ".".join(network.split(".")[:3])

        async with httpx.AsyncClient(timeout=2.0) as client:
            for i in range(1, 255):
                ip = f"{base}.{i}"
                try:
                    resp = await client.get(f"http://{ip}/api/about")
                    if resp.status_code == 200:
                        data = resp.json()
                        info = data.get("info", {})
                        devices.append(DiscoveredDevice(
                            host=ip,
                            port=80,
                            name=f"{info.get('brand', '')} {info.get('model', '')}".strip(),
                            device_type="enigma2",
                            model=info.get("model", ""),
                        ))
                except Exception:
                    continue

        return devices
