"""
ADB STB Adapter for Android-based STBs.
Communicates via Android Debug Bridge (ADB) over TCP.
"""

import asyncio
import os
from typing import Optional
from pathlib import Path

from adb_shell.auth.keygen import keygen
from adb_shell.auth.sign_pythonrsa import PythonRSASigner
from adb_shell.adb_device_async import AdbDeviceTcpAsync

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
from backend.core.config import get_config

log = get_logger("adb_adapter")

# Mapping our standard keys to Android KeyEvents
# https://developer.android.com/reference/android/view/KeyEvent
ADB_KEYCODES = {
    "POWER": 26,       # KEYCODE_POWER
    "OK": 66,          # KEYCODE_ENTER / DPAD_CENTER
    "ENTER": 66,
    "UP": 19,          # KEYCODE_DPAD_UP
    "DOWN": 20,        # KEYCODE_DPAD_DOWN
    "LEFT": 21,        # KEYCODE_DPAD_LEFT
    "RIGHT": 22,       # KEYCODE_DPAD_RIGHT
    "MENU": 82,        # KEYCODE_MENU
    "EXIT": 4,         # KEYCODE_BACK
    "BACK": 4,         # KEYCODE_BACK
    "VOL_UP": 24,      # KEYCODE_VOLUME_UP
    "VOL_DOWN": 25,    # KEYCODE_VOLUME_DOWN
    "MUTE": 164,       # KEYCODE_VOLUME_MUTE
    "CH_UP": 166,      # KEYCODE_CHANNEL_UP
    "CH_DOWN": 167,    # KEYCODE_CHANNEL_DOWN
    "EPG": 172,        # KEYCODE_GUIDE
    "INFO": 165,       # KEYCODE_INFO
    "RED": 183,        # KEYCODE_PROG_RED
    "GREEN": 184,      # KEYCODE_PROG_GREEN
    "YELLOW": 185,     # KEYCODE_PROG_YELLOW
    "BLUE": 186,       # KEYCODE_PROG_BLUE
    "0": 7,            # KEYCODE_0
    "1": 8,            # KEYCODE_1
    "2": 9,            # KEYCODE_2
    "3": 10,           # KEYCODE_3
    "4": 11,           # KEYCODE_4
    "5": 12,           # KEYCODE_5
    "6": 13,           # KEYCODE_6
    "7": 14,           # KEYCODE_7
    "8": 15,           # KEYCODE_8
    "9": 16,           # KEYCODE_9
    "PLAY": 126,       # KEYCODE_MEDIA_PLAY
    "PAUSE": 127,      # KEYCODE_MEDIA_PAUSE
    "STOP": 86,        # KEYCODE_MEDIA_STOP
    "REC": 130,        # KEYCODE_MEDIA_RECORD
    "FF": 90,          # KEYCODE_MEDIA_FAST_FORWARD
    "REW": 89,         # KEYCODE_MEDIA_REWIND
}


class ADBAdapter(STBAdapter):
    """
    Adapter for Android-based STBs via ADB over network.
    Particularly useful for Android partition on dual-boot STBs (like Qviart Dual).
    """

    def __init__(self, host: str, port: int = 5555, credentials: dict = None, options: dict = None):
        if port == 0:
            port = 5555
        super().__init__(host, port, credentials, options)
        
        self.device = AdbDeviceTcpAsync(self.host, self.port, default_transport_timeout_s=5.0)
        self.signer = self._get_or_create_adb_keys()
        
        # State tracking (ADB doesn't provide easy hooks for these, so we guess/poll)
        self._current_app = ""
        self._volume = 50
        self._muted = False
        
    def _get_or_create_adb_keys(self) -> PythonRSASigner:
        """Load or generate ADB RSA keys for authentication."""
        config = get_config()
        data_dir = Path(config.database_path).parent
        key_path = data_dir / "adbkey"
        
        if not key_path.exists():
            log.info("adb_generating_keys", path=str(key_path))
            keygen(str(key_path))
            
        with open(str(key_path), "r") as f:
            priv = f.read()
            
        with open(str(key_path) + ".pub", "r") as f:
            pub = f.read()
            
        return PythonRSASigner(pub, priv)

    # ──── Connection ────

    async def connect(self) -> bool:
        try:
            # ADB over TCP typically uses port 5555
            result = await self.device.connect(rsa_keys=[self.signer], auth_timeout_s=5.0)
            self._connected = result
            if result:
                log.info("adb_connected", host=self.host)
                # Try to wake up / get initial state
                await self.device.shell("input keyevent KEYCODE_WAKEUP")
            else:
                log.warning("adb_connect_failed_auth_required", host=self.host)
            return result
        except BaseException as e:
            log.error("adb_connect_failed", host=self.host, error=str(e))
            self._connected = False
            return False

    async def disconnect(self):
        if self._connected:
            await self.device.close()
            self._connected = False
            log.info("adb_disconnected", host=self.host)

    async def check_health(self) -> bool:
        if not self._connected:
            return await self.connect()
        try:
            # Simple echo to test connection
            res = await self.device.shell("echo 1", timeout_s=2.0)
            return res.strip() == "1"
        except Exception:
            self._connected = False
            return False

    # ──── Status ────

    async def get_status(self) -> STBStatus:
        if not self._connected:
            await self.connect()
            
        if not self._connected:
            return STBStatus(device_name="Android STB (Offline)")
            
        try:
            # Check screen state (standby)
            dumpsys_power = await self.device.shell("dumpsys power | grep 'mHoldingDisplaySuspendBlocker'", timeout_s=2.0)
            in_standby = "false" in (dumpsys_power or "").lower()
            
            # Get current foreground app package
            current_app_raw = await self.device.shell("dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'", timeout_s=2.0)
            current_app = ""
            if current_app_raw:
                try:
                    current_app = current_app_raw.split("/")[-2].split(" ")[-1]
                except IndexError:
                    pass
                    
            # Try to get device name
            model = await self.device.shell("getprop ro.product.model", timeout_s=2.0)
            model = model.strip() if model else "Android STB"

            return STBStatus(
                in_standby=in_standby,
                current_channel=current_app if not in_standby else "Apagado",
                current_channel_ref=current_app,
                current_program="N/A (Limitación Android)",
                volume=self._volume,
                is_muted=self._muted,
                device_name=model,
                device_model=model,
            )
        except Exception as e:
            log.error("adb_status_failed", error=str(e))
            return STBStatus(device_name="Android STB (Error)")

    # ──── Remote Control ────

    async def send_key(self, key: str, key_type: str = "short") -> KeyPressResponse:
        if not self._connected:
            if not await self.connect():
                return KeyPressResponse(result=False, message="Not connected")
                
        key_upper = key.upper()
        if key_upper not in ADB_KEYCODES:
            return KeyPressResponse(result=False, message=f"Unknown key: {key}")

        keycode = ADB_KEYCODES[key_upper]
        try:
            if key_type == "long":
                # ADB doesn't easily support long press, simulation requires swipe or sendevent (root)
                # Fallback to multiple short presses or just single short press for now
                await self.device.shell(f"input keyevent {keycode}")
            else:
                await self.device.shell(f"input keyevent {keycode}")
                
            # Track local volume state
            if key_upper == "VOL_UP":
                self._volume = min(100, self._volume + 5)
            elif key_upper == "VOL_DOWN":
                self._volume = max(0, self._volume - 5)
            elif key_upper == "MUTE":
                self._muted = not self._muted
                
            return KeyPressResponse(result=True, message=f"Key {key} sent")
        except Exception as e:
            self._connected = False
            return KeyPressResponse(result=False, message=str(e))

    # ──── Channels, EPG, Timers ────
    # For Android without a specific App API, these are usually unavailable
    # unless we reverse engineer the specific app intent or database.
    # We return empty/mock data for these interfaces so the UI doesn't break.

    async def get_bouquets(self) -> list[Bouquet]:
        return []

    async def get_channels(self, bouquet_ref: Optional[str] = None) -> list[Channel]:
        return []

    async def zap(self, service_ref: str) -> ZapResponse:
        # Launch app intent if service_ref looks like a package name
        if "." in service_ref and not ":" in service_ref:
            try:
                await self.device.shell(f"monkey -p {service_ref} -c android.intent.category.LAUNCHER 1")
                return ZapResponse(result=True, message=f"Launched {service_ref}", channel_name=service_ref)
            except Exception:
                pass
        return ZapResponse(result=False, message="Not supported on Android generic ADB")

    async def get_epg_now_next(self, bouquet_ref: Optional[str] = None) -> list[EPGNowNext]:
        return []

    async def get_epg_service(self, service_ref: str) -> list[EPGEvent]:
        return []

    async def get_volume(self) -> VolumeState:
        return VolumeState(volume=self._volume, is_muted=self._muted)

    async def set_volume(self, action: str, value: Optional[int] = None) -> VolumeState:
        if action == "up":
            await self.send_key("VOL_UP")
        elif action == "down":
            await self.send_key("VOL_DOWN")
        elif action == "mute":
            await self.send_key("MUTE")
        return await self.get_volume()

    async def get_timers(self) -> list[Timer]:
        return []

    async def add_timer(self, timer: Timer) -> TimerResponse:
        return TimerResponse(result=False, message="Not supported on generic Android")

    async def delete_timer(self, service_ref: str, begin_time: str, end_time: str) -> TimerResponse:
        return TimerResponse(result=False, message="Not supported")

    # ──── Power ────

    async def set_power_state(self, action: str) -> bool:
        try:
            if action in ("toggle", "standby", "wakeup"):
                await self.send_key("POWER")
            elif action == "reboot":
                await self.device.shell("reboot")
            return True
        except Exception:
            return False

    # ──── Discovery ────

    @staticmethod
    async def discover(network: str = "192.168.1.0/24") -> list[DiscoveredDevice]:
        # Would require trying port 5555 across the subnet
        return []
