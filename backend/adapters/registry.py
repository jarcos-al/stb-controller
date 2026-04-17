"""
Adapter registry and factory.
Maps adapter type names to their implementations and manages active instances.
"""

from typing import Optional
from backend.adapters.base import STBAdapter
from backend.adapters.mock import MockAdapter
from backend.adapters.enigma2 import Enigma2Adapter
from backend.adapters.adb import ADBAdapter
from backend.adapters.gmscreen import GMScreenAdapter
from backend.core.config import DeviceConfig
from backend.core.logging import get_logger

log = get_logger("adapter_registry")

# Registry of available adapter types
ADAPTER_TYPES: dict[str, type[STBAdapter]] = {
    "mock": MockAdapter,
    "enigma2": Enigma2Adapter,
    "adb": ADBAdapter,
    "gmscreen": GMScreenAdapter,
    # "ir_broadlink": IRBridgeAdapter,  # Future
}

# Active adapter instances keyed by device ID
_active_adapters: dict[int, STBAdapter] = {}


def create_adapter(device_config: DeviceConfig, device_id: int = 0) -> STBAdapter:
    """
    Create and register an adapter instance from device config.

    Args:
        device_config: Configuration for the device
        device_id: Unique ID for the device instance
    """
    adapter_type = device_config.adapter
    if adapter_type not in ADAPTER_TYPES:
        log.warning("unknown_adapter_type", adapter=adapter_type, fallback="mock")
        adapter_type = "mock"

    adapter_class = ADAPTER_TYPES[adapter_type]
    adapter = adapter_class(
        host=device_config.host,
        port=device_config.port,
        credentials=device_config.credentials,
        options=device_config.options,
    )

    _active_adapters[device_id] = adapter
    log.info("adapter_created", type=adapter_type, device_id=device_id, host=device_config.host)
    return adapter


def get_adapter(device_id: int = 0) -> Optional[STBAdapter]:
    """Get an active adapter by device ID."""
    return _active_adapters.get(device_id)


def get_default_adapter() -> Optional[STBAdapter]:
    """Get the first active adapter (default device)."""
    if _active_adapters:
        return next(iter(_active_adapters.values()))
    return None


def list_adapters() -> dict[int, STBAdapter]:
    """Get all active adapters."""
    return _active_adapters.copy()


async def disconnect_all():
    """Disconnect all active adapters."""
    for device_id, adapter in _active_adapters.items():
        try:
            await adapter.disconnect()
            log.info("adapter_disconnected", device_id=device_id)
        except Exception as e:
            log.error("adapter_disconnect_failed", device_id=device_id, error=str(e))
    _active_adapters.clear()
