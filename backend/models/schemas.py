"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ──── Device Schemas ────

class DeviceBase(BaseModel):
    name: str
    host: str
    port: int = 80
    adapter_type: str = "mock"


class DeviceCreate(DeviceBase):
    credentials: dict = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)


class DeviceResponse(DeviceBase):
    id: int
    status: str = "unknown"
    last_seen: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ──── STB Status Schemas ────

class STBStatus(BaseModel):
    """Current state of the STB device."""
    in_standby: bool = False
    current_channel: str = ""
    current_channel_ref: str = ""
    current_program: str = ""
    program_description: str = ""
    program_start: Optional[str] = None
    program_end: Optional[str] = None
    volume: int = 50
    is_muted: bool = False
    is_recording: bool = False
    signal_strength: Optional[int] = None
    signal_snr: Optional[int] = None
    device_name: str = ""
    device_model: str = ""


# ──── Remote Control Schemas ────

class KeyPress(BaseModel):
    """Remote control key press command."""
    key: str  # Named key (e.g., "OK", "UP", "VOL_UP", "1", "POWER")
    key_type: str = "short"  # short | long


class KeyPressResponse(BaseModel):
    result: bool
    message: str = ""


# ──── Channel Schemas ────

class Channel(BaseModel):
    id: Optional[int] = None
    name: str
    service_ref: str
    provider: str = ""
    is_hd: bool = False
    is_favorite: bool = False
    channel_number: int = 0

    model_config = {"from_attributes": True}


class Bouquet(BaseModel):
    id: Optional[int] = None
    name: str
    service_ref: str = ""
    channels: list[Channel] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ZapRequest(BaseModel):
    service_ref: str


class ZapResponse(BaseModel):
    result: bool
    message: str = ""
    channel_name: str = ""


# ──── EPG Schemas ────

class EPGEvent(BaseModel):
    event_id: Optional[int] = None
    title: str
    description: str = ""
    description_ext: str = ""
    start_time: str
    duration: int = 0  # seconds
    service_ref: str = ""
    channel_name: str = ""
    genre: str = ""


class EPGNowNext(BaseModel):
    """Current and next program for a channel."""
    channel_name: str
    service_ref: str
    now: Optional[EPGEvent] = None
    next: Optional[EPGEvent] = None


# ──── Timer Schemas ────

class TimerBase(BaseModel):
    service_ref: str
    channel_name: str = ""
    begin_time: str
    end_time: str
    name: str
    description: str = ""
    repeated: int = 0
    repeated_days: str = ""


class TimerCreate(TimerBase):
    pass


class Timer(TimerBase):
    id: Optional[int] = None
    stb_id: Optional[int] = None
    state: int = 0  # 0=waiting, 1=running, 2=finished, 3=disabled

    model_config = {"from_attributes": True}


class TimerResponse(BaseModel):
    result: bool
    message: str = ""


# ──── Volume Schemas ────

class VolumeState(BaseModel):
    volume: int
    is_muted: bool


class VolumeCommand(BaseModel):
    action: str  # "up", "down", "mute", "set"
    value: Optional[int] = None  # For "set" action


# ──── Power Schemas ────

class PowerCommand(BaseModel):
    action: str  # "toggle", "standby", "wakeup", "reboot", "deep_standby"


# ──── Discovery Schemas ────

class DiscoveredDevice(BaseModel):
    host: str
    port: int
    name: str = ""
    device_type: str = ""  # enigma2, gmscreen, android, unknown
    model: str = ""


# ──── WebSocket Message Schemas ────

class WSMessage(BaseModel):
    type: str  # "keypress", "status_update", "channel_changed", "error", "heartbeat"
    data: dict = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ──── API Response Wrappers ────

class APIResponse(BaseModel):
    result: bool
    message: str = ""
    data: Optional[dict] = None
