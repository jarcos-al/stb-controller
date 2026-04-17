"""
Abstract Base Class for STB adapters.
All adapter implementations must inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Optional

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


class STBAdapter(ABC):
    """
    Abstract interface for STB device communication.

    Each adapter implementation handles the protocol-specific details
    of communicating with a particular type of STB device.
    """

    def __init__(self, host: str, port: int, credentials: dict = None, options: dict = None):
        self.host = host
        self.port = port
        self.credentials = credentials or {}
        self.options = options or {}
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ──── Connection ────

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the STB device."""
        ...

    @abstractmethod
    async def disconnect(self):
        """Close connection to the STB device."""
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        """Check if the device is reachable and responsive."""
        ...

    # ──── Status ────

    @abstractmethod
    async def get_status(self) -> STBStatus:
        """Get current status of the STB device."""
        ...

    # ──── Remote Control ────

    @abstractmethod
    async def send_key(self, key: str, key_type: str = "short") -> KeyPressResponse:
        """
        Send a remote control key press.

        Args:
            key: Named key (e.g., "OK", "UP", "VOL_UP", "1", "POWER")
            key_type: "short" for normal press, "long" for long press
        """
        ...

    # ──── Channels ────

    @abstractmethod
    async def get_bouquets(self) -> list[Bouquet]:
        """Get list of channel bouquets/groups."""
        ...

    @abstractmethod
    async def get_channels(self, bouquet_ref: Optional[str] = None) -> list[Channel]:
        """
        Get list of channels, optionally filtered by bouquet.

        Args:
            bouquet_ref: Service reference of a bouquet to filter by
        """
        ...

    @abstractmethod
    async def zap(self, service_ref: str) -> ZapResponse:
        """
        Change to a specific channel.

        Args:
            service_ref: Service reference string of the target channel
        """
        ...

    # ──── EPG ────

    @abstractmethod
    async def get_epg_now_next(self, bouquet_ref: Optional[str] = None) -> list[EPGNowNext]:
        """Get current and next program for channels in a bouquet."""
        ...

    @abstractmethod
    async def get_epg_service(self, service_ref: str) -> list[EPGEvent]:
        """Get EPG events for a specific service/channel."""
        ...

    async def search_epg(self, query: str) -> list[EPGEvent]:
        """Search EPG by title. Override in adapters that support it."""
        return []

    # ──── Volume ────

    @abstractmethod
    async def get_volume(self) -> VolumeState:
        """Get current volume level and mute state."""
        ...

    @abstractmethod
    async def set_volume(self, action: str, value: Optional[int] = None) -> VolumeState:
        """
        Control volume.

        Args:
            action: "up", "down", "mute", "set"
            value: Volume level (0-100) for "set" action
        """
        ...

    # ──── Timers ────

    @abstractmethod
    async def get_timers(self) -> list[Timer]:
        """Get list of scheduled timers."""
        ...

    @abstractmethod
    async def add_timer(self, timer: Timer) -> TimerResponse:
        """Schedule a new timer."""
        ...

    @abstractmethod
    async def delete_timer(self, service_ref: str, begin_time: str, end_time: str) -> TimerResponse:
        """Delete a scheduled timer."""
        ...

    # ──── Power ────

    @abstractmethod
    async def set_power_state(self, action: str) -> bool:
        """
        Control power state.

        Args:
            action: "toggle", "standby", "wakeup", "reboot", "deep_standby"
        """
        ...

    # ──── Discovery (class method) ────

    @staticmethod
    async def discover(network: str = "192.168.1.0/24") -> list[DiscoveredDevice]:
        """
        Discover STB devices on the local network.
        Override in subclasses for protocol-specific discovery.
        """
        return []

    # ──── Stream (optional) ────

    async def get_stream_url(self, service_ref: str) -> Optional[str]:
        """Get streaming URL for a channel. Returns None if not supported."""
        return None

    # ──── String representation ────

    def __repr__(self):
        return f"<{self.__class__.__name__} host={self.host}:{self.port} connected={self._connected}>"
