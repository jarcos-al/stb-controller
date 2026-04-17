"""
G-MScreen STB Adapter.
Communicates via the proprietary TCP protocol (default port 20000) used by ALi/Guoxin chipsets.
"""

import asyncio
import xml.etree.ElementTree as ET
import zlib
from typing import Optional

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

log = get_logger("gmscreen_adapter")

# Confirmed key map from explore_keys.py + retest_keys.py sessions
GMSCREEN_KEYS = {
    # ── D-pad ──
    "UP": "1",
    "DOWN": "2",
    "LEFT": "3",
    "RIGHT": "4",
    "OK": "5",
    # ── Navigation ──
    "MENU": "6",
    "EXIT": "7",
    "INFO": "22",
    "BACK": "29",
    "SAT": "30",
    "EPG": "32",
    "TEXT": "34",
    "TIMER": "26",
    # ── Colors ──
    "RED": "8",
    "GREEN": "9",
    "YELLOW": "10",
    "BLUE": "11",
    # ── Numbers ──
    "0": "12",
    "1": "13",
    "2": "14",
    "3": "15",
    "4": "16",
    "5": "17",
    "6": "18",
    "7": "19",
    "8": "20",
    "9": "21",
    # ── Volume / Channel ──
    "MUTE": "23",
    "VOL_UP": "35",
    "VOL_DOWN": "36",
    "CH_UP": "37",
    "CH_DOWN": "38",
    # ── Power ──
    "POWER": "42",
    # ── Subtitle ──
    "SUBTITLE": "31",
    # ── Playback ──
    "REC": "58",
    "PLAY": "61",
    "STOP": "62",
    "PAUSE": "63",
}

class GMScreenAdapter(STBAdapter):
    """
    Adapter for STBs running the G-MScreen TCP service (typically port 20000).
    """

    def __init__(self, host: str, port: int = 20000, credentials: dict = None, options: dict = None):
        if port == 0:
            port = 20000
        super().__init__(host, port, credentials, options)
        
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._lock = asyncio.Lock()
        self._channels_cache: dict[str, str] = {}  # pid → name
        self.serial_number: str = ""
        self.product_name: str = ""
        self.software_version: str = ""

    XML_HEADER = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"

    # ──── Connection ────

    def _build_packet(self, xml_body: str) -> bytes:
        """Build a Start/End protocol packet."""
        full_xml = f"{self.XML_HEADER}{xml_body}"
        length_str = str(len(full_xml)).zfill(7)
        return f"Start{length_str}End{full_xml}".encode('utf-8')

    async def _read_gcdh(self, timeout: float = 5.0) -> Optional[str]:
        """Read a GCDH response (header + zlib payload). Must be called with lock held."""
        try:
            header = await asyncio.wait_for(self.reader.readexactly(16), timeout=timeout)
            if not header.startswith(b'GCDH'):
                log.error("gmscreen_malformed_header", header=header)
                return ""
            payload_len = int.from_bytes(header[4:8], byteorder='little')
            payload_bytes = await asyncio.wait_for(
                self.reader.readexactly(payload_len), timeout=timeout
            )
            if payload_bytes.startswith((b'\x78\x9c', b'\x78\xda', b'\x78\x01')):
                try:
                    payload_bytes = zlib.decompress(payload_bytes)
                except Exception as e:
                    log.warning("gmscreen_zlib_error", error=str(e))
            return payload_bytes.decode('utf-8', errors='ignore').strip()
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            log.error("gmscreen_read_error", error=str(e))
            return None

    async def _send_raw(self, xml_payload: str, timeout: float = 5.0) -> Optional[str]:
        """Send command and read GCDH response. Must be called with lock held."""
        try:
            self.writer.write(self._build_packet(xml_payload))
            await self.writer.drain()
            return await self._read_gcdh(timeout)
        except Exception as e:
            log.error("gmscreen_send_error", error=str(e))
            return None

    async def _handshake(self):
        """Perform the device registration handshake. Must be called with lock held."""
        # req=998: returns RAW 108 bytes (not GCDH)
        reg_xml = (
            '<Command request="998"><parm>'
            '<DeviceName>STBControl</DeviceName>'
            '<DeviceModel>WebPanel</DeviceModel>'
            '<UUID>stb-control-web-001</UUID>'
            '</parm></Command>'
        )
        self.writer.write(self._build_packet(reg_xml))
        await self.writer.drain()
        try:
            await asyncio.wait_for(self.reader.read(256), timeout=5.0)
        except Exception:
            pass

        # Follow-up handshake requests
        for req_id in [32, 18, 22, 20, 16, 15]:
            resp = await self._send_raw(f'<Command request="{req_id}" />')
            if req_id == 15 and resp:
                try:
                    root = ET.fromstring(resp)
                    self.product_name = root.findtext('.//ProductName', '')
                    self.serial_number = root.findtext('.//SerialNumber', '')
                    self.software_version = root.findtext('.//SoftwareVersion', '')
                    log.info("gmscreen_device_info",
                             product=self.product_name,
                             serial=self.serial_number,
                             version=self.software_version)
                except Exception:
                    pass

    async def connect(self) -> bool:
        async with self._lock:
            if self._connected and self.writer:
                return True
            try:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=5.0
                )
                self._connected = True
                await self._handshake()
                log.info("gmscreen_connected", host=self.host, port=self.port)
                return True
            except BaseException as e:
                log.error("gmscreen_connect_failed", host=self.host, error=str(e))
                self._connected = False
                return False

    async def disconnect(self):
        async with self._lock:
            if self.writer:
                try:
                    self.writer.close()
                    await self.writer.wait_closed()
                except Exception:
                    pass
            self.reader = None
            self.writer = None
            self._connected = False
            log.info("gmscreen_disconnected")

    async def check_health(self) -> bool:
        if not self._connected:
            return False
        # Enviar comando 26 (Status/Ping detectado en captura)
        result = await self._send_command('<Command request="26" />')
        return result is not None

    async def _send_command(self, xml_payload: str) -> Optional[str]:
        """Send a command and read GCDH response."""
        if not self._connected:
            return None
        async with self._lock:
            log.debug("gmscreen_tx", payload=xml_payload[:80])
            result = await self._send_raw(xml_payload)
            if result is None:
                self._connected = False
            else:
                log.debug("gmscreen_rx", response_snippet=result[:100])
            return result

    async def _send_fire_and_forget(self, xml_payload: str) -> bool:
        """Send a command without waiting for a response (for key presses)."""
        if not self._connected:
            return False
        async with self._lock:
            try:
                log.debug("gmscreen_tx_ff", payload=xml_payload[:80])
                self.writer.write(self._build_packet(xml_payload))
                await self.writer.drain()
                # Drain any unsolicited response that might arrive
                try:
                    await asyncio.wait_for(self.reader.read(4096), timeout=0.15)
                except asyncio.TimeoutError:
                    pass
                return True
            except Exception as e:
                log.error("gmscreen_send_error", error=str(e))
                self._connected = False
                return False

    # ──── Status ────

    async def get_status(self) -> STBStatus:
        # req=3 returns current channel ProgramId
        response = await self._send_command('<Command request="3" />')
        if response is None:
            return STBStatus(device_name="Qviart Dual (Offline)")

        current_ref = ""
        current_name = ""
        try:
            root = ET.fromstring(response)
            current_ref = root.findtext('.//Data', '')
        except Exception:
            pass

        # Look up channel name from cache
        if current_ref and current_ref in self._channels_cache:
            current_name = self._channels_cache[current_ref]

        return STBStatus(
            in_standby=False,
            current_channel=current_name,
            current_channel_ref=current_ref,
            current_program="",

            device_name="Qviart Dual",
            device_model="ALi/GMScreen",
        )

    # ──── Remote Control ────

    async def send_key(self, key: str, key_type: str = "short") -> KeyPressResponse:
        key_upper = key.upper()
        # Allow raw numeric values for testing (e.g. "RAW_33")
        if key_upper.startswith("RAW_") and key_upper[4:].isdigit():
            key_value = key_upper[4:]
        elif key_upper not in GMSCREEN_KEYS:
            return KeyPressResponse(result=False, message=f"Unmapped key: {key}")
        else:
            key_value = GMSCREEN_KEYS[key_upper]
        
        xml_cmd = f'<Command request="1040"><parm><KeyValue>{key_value}</KeyValue></parm></Command>'
        
        success = await self._send_fire_and_forget(xml_cmd)
        
        if success:
            return KeyPressResponse(result=True, message=f"Key {key} sent ({key_value})")
        else:
            return KeyPressResponse(result=False, message="Failed to reach STB")

    # ──── Resto de APIs ────
    
    async def get_bouquets(self) -> list[Bouquet]:
        # req=12 returns favorite groups
        response = await self._send_command('<Command request="12" />')
        if not response:
            return []
        try:
            root = ET.fromstring(response)
            bouquets = []
            for parm in root.findall('.//parm'):
                name = parm.findtext('favorGroupName', '')
                if name:
                    bouquets.append(Bouquet(name=name, service_ref=name))
            return bouquets
        except Exception as e:
            log.error("gmscreen_bouquets_parse_error", error=str(e))
            return []

    async def get_channels(self, bouquet_ref: Optional[str] = None) -> list[Channel]:
        all_programs = []
        page_size = 100
        from_idx = 0
        while True:
            to_idx = from_idx + page_size - 1
            xml_cmd = (
                f'<Command request="0"><parm>'
                f'<FromIndex>{from_idx}</FromIndex>'
                f'<ToIndex>{to_idx}</ToIndex>'
                f'</parm></Command>'
            )
            response = await self._send_command(xml_cmd)
            if not response:
                break
            try:
                root = ET.fromstring(response)
                programs = root.findall('.//parm')
                if not programs:
                    break
                for parm in programs:
                    pid = parm.findtext('ProgramId', '')
                    name = parm.findtext('ProgramName', '')
                    is_hd = parm.findtext('IsProgramHD', '0') == '1'
                    channel_type = parm.findtext('ChannelType', '1')
                    fav_group = parm.findtext('FavorGroupID', '')
                    if pid and name:
                        all_programs.append({
                            'pid': pid, 'name': name, 'is_hd': is_hd,
                            'channel_type': channel_type, 'fav_group': fav_group,
                        })
                if len(programs) < page_size:
                    break
                from_idx += page_size
            except Exception as e:
                log.error("gmscreen_channels_parse_error", error=str(e))
                break

        # Build cache for all channels (used by get_status)
        self._channels_cache = {p['pid']: p['name'] for p in all_programs}

        # Filter: ChannelType=0 means TV, ChannelType=1 means Radio
        # If bouquet_ref is specified, filter by FavorGroupID
        tv_channels = [p for p in all_programs if p['channel_type'] == '0']

        if bouquet_ref:
            # bouquet_ref is the bouquet name; find its 1-based index
            bouquets = await self.get_bouquets()
            bq_idx = None
            for i, bq in enumerate(bouquets):
                if bq.service_ref == bouquet_ref or bq.name == bouquet_ref:
                    bq_idx = i + 1  # 1-based in FavorGroupID
                    break
            if bq_idx is not None:
                tv_channels = [
                    p for p in tv_channels
                    if f'{bq_idx}:' in (p['fav_group'] or '')
                ]

        channels = []
        for i, p in enumerate(tv_channels):
            channels.append(Channel(
                name=p['name'],
                service_ref=p['pid'],
                is_hd=p['is_hd'],
                channel_number=i + 1,
            ))

        log.info("gmscreen_channels_loaded", count=len(channels), total=len(all_programs))
        return channels

    async def zap(self, service_ref: str) -> ZapResponse:
        if not self._connected:
            if not await self.connect():
                return ZapResponse(result=False, message="Not connected")
        xml_cmd = (
            f'<Command request="1000"><parm>'
            f'<TvState>0</TvState>'
            f'<ProgramId>{service_ref}</ProgramId>'
            f'<iResolutionRatio>0</iResolutionRatio>'
            f'<iBitrate>0</iBitrate>'
            f'</parm></Command>'
        )
        async with self._lock:
            try:
                # Drain any stale data before zapping
                if self.reader and self.reader._buffer:
                    self.reader._buffer.clear()
                self.writer.write(self._build_packet(xml_cmd))
                await self.writer.drain()
                # Zap response is empty (8B zlib → ""), just try to read it
                # but don't fail if it times out — the zap still works
                try:
                    await self._read_gcdh(timeout=2.0)
                except Exception:
                    pass
                return ZapResponse(result=True, message=f"Zapped to {service_ref}")
            except Exception as e:
                log.error("gmscreen_zap_error", error=str(e))
                return ZapResponse(result=False, message=str(e))

    async def get_epg_now_next(self, bouquet_ref: Optional[str] = None) -> list[EPGNowNext]:
        return []

    async def get_epg_service(self, service_ref: str) -> list[EPGEvent]:
        return []

    async def get_volume(self) -> VolumeState:
        return VolumeState(volume=50, is_muted=False)

    async def set_volume(self, action: str, value: Optional[int] = None) -> VolumeState:
        return await self.get_volume()

    async def get_timers(self) -> list[Timer]:
        return []

    async def add_timer(self, timer: Timer) -> TimerResponse:
        return TimerResponse(result=False)

    async def delete_timer(self, service_ref: str, begin_time: str, end_time: str) -> TimerResponse:
        return TimerResponse(result=False)

    async def set_power_state(self, action: str) -> bool:
        return False
