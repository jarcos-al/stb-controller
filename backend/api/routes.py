"""
API routes for device management and STB control.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from backend.core.auth import verify_auth
from backend.core.websocket import ws_manager
from backend.adapters.registry import (
    get_adapter, get_default_adapter, list_adapters,
    create_adapter, _active_adapters,
)
from backend.core.config import DeviceConfig
from backend.models.schemas import (
    STBStatus,
    KeyPress,
    KeyPressResponse,
    Channel,
    Bouquet,
    ZapRequest,
    ZapResponse,
    EPGEvent,
    EPGNowNext,
    Timer,
    TimerCreate,
    TimerResponse,
    VolumeState,
    VolumeCommand,
    PowerCommand,
    APIResponse,
)
from backend.core.logging import get_logger

log = get_logger("api")

router = APIRouter(prefix="/api", tags=["STB Control"])


def _get_adapter(device_id: int = 0):
    """Get adapter by device ID or default."""
    if device_id == 0:
        adapter = get_default_adapter()
    else:
        adapter = get_adapter(device_id)

    if adapter is None:
        raise HTTPException(status_code=404, detail="No STB device configured")
    return adapter


# ──── Health & Status ────

@router.get("/health")
async def health_check():
    """Health check endpoint for Docker/monitoring."""
    adapter = get_default_adapter()
    stb_ok = False
    if adapter:
        try:
            stb_ok = await adapter.check_health()
        except Exception:
            pass

    return {
        "status": "ok",
        "stb_connected": stb_ok,
        "ws_clients": ws_manager.client_count,
    }


@router.get("/status", response_model=STBStatus, dependencies=[Depends(verify_auth)])
async def get_status(device_id: int = 0):
    """Get current STB status."""
    adapter = _get_adapter(device_id)
    return await adapter.get_status()


@router.post("/device/connect", dependencies=[Depends(verify_auth)])
async def device_connect(device_id: int = 0):
    """Connect to the STB device."""
    adapter = _get_adapter(device_id)
    connected = await adapter.connect()
    if connected:
        # Pre-load channels cache
        try:
            await adapter.get_channels()
        except Exception:
            pass
    return {"connected": connected}


@router.post("/device/disconnect", dependencies=[Depends(verify_auth)])
async def device_disconnect(device_id: int = 0):
    """Disconnect from the STB device."""
    adapter = _get_adapter(device_id)
    await adapter.disconnect()
    return {"connected": False}


@router.get("/devices", dependencies=[Depends(verify_auth)])
async def get_devices():
    """List all configured STB devices."""
    adapters = list_adapters()
    devices = []
    for dev_id, adapter in adapters.items():
        try:
            healthy = await adapter.check_health()
        except Exception:
            healthy = False

        devices.append({
            "id": dev_id,
            "host": adapter.host,
            "port": adapter.port,
            "type": adapter.__class__.__name__.replace("Adapter", "").lower(),
            "connected": adapter.is_connected,
            "healthy": healthy,
        })
    return {"devices": devices}


# ──── Remote Control ────

@router.post("/remote/key", response_model=KeyPressResponse, dependencies=[Depends(verify_auth)])
async def send_key(cmd: KeyPress, device_id: int = 0):
    """Send a remote control key press to the STB."""
    adapter = _get_adapter(device_id)
    result = await adapter.send_key(cmd.key, cmd.key_type)

    # Broadcast state update after key press
    if result.result:
        try:
            status = await adapter.get_status()
            await ws_manager.broadcast_status(status.model_dump())
        except Exception:
            pass

    return result


# ──── Channels ────

@router.get("/bouquets", response_model=list[Bouquet], dependencies=[Depends(verify_auth)])
async def get_bouquets(device_id: int = 0):
    """Get list of channel bouquets."""
    adapter = _get_adapter(device_id)
    return await adapter.get_bouquets()


@router.get("/channels", response_model=list[Channel], dependencies=[Depends(verify_auth)])
async def get_channels(
    device_id: int = 0,
    bouquet_ref: Optional[str] = Query(None, alias="bouquet"),
):
    """Get list of channels, optionally filtered by bouquet."""
    adapter = _get_adapter(device_id)
    return await adapter.get_channels(bouquet_ref)


@router.post("/channels/zap", response_model=ZapResponse, dependencies=[Depends(verify_auth)])
async def zap_channel(cmd: ZapRequest, device_id: int = 0):
    """Change to a specific channel."""
    adapter = _get_adapter(device_id)
    result = await adapter.zap(cmd.service_ref)

    if result.result:
        await ws_manager.broadcast_channel_changed(result.channel_name, cmd.service_ref)

    return result


# ──── EPG ────

@router.get("/epg/nownext", response_model=list[EPGNowNext], dependencies=[Depends(verify_auth)])
async def get_epg_now_next(
    device_id: int = 0,
    bouquet_ref: Optional[str] = Query(None, alias="bouquet"),
):
    """Get current and next programs for channels."""
    adapter = _get_adapter(device_id)
    return await adapter.get_epg_now_next(bouquet_ref)


@router.get("/epg/service/{service_ref:path}", response_model=list[EPGEvent], dependencies=[Depends(verify_auth)])
async def get_epg_service(service_ref: str, device_id: int = 0):
    """Get EPG events for a specific channel."""
    adapter = _get_adapter(device_id)
    return await adapter.get_epg_service(service_ref)


@router.get("/epg/search", response_model=list[EPGEvent], dependencies=[Depends(verify_auth)])
async def search_epg(
    q: str = Query(..., min_length=2),
    device_id: int = 0,
):
    """Search EPG by title."""
    adapter = _get_adapter(device_id)
    return await adapter.search_epg(q)


# ──── Volume ────

@router.get("/volume", response_model=VolumeState, dependencies=[Depends(verify_auth)])
async def get_volume(device_id: int = 0):
    """Get current volume state."""
    adapter = _get_adapter(device_id)
    return await adapter.get_volume()


@router.post("/volume", response_model=VolumeState, dependencies=[Depends(verify_auth)])
async def set_volume(cmd: VolumeCommand, device_id: int = 0):
    """Control volume (up, down, mute, set)."""
    adapter = _get_adapter(device_id)
    result = await adapter.set_volume(cmd.action, cmd.value)

    # Broadcast volume change
    await ws_manager.broadcast({
        "type": "volume_changed",
        "data": result.model_dump(),
    })

    return result


# ──── Timers ────

@router.get("/timers", response_model=list[Timer], dependencies=[Depends(verify_auth)])
async def get_timers(device_id: int = 0):
    """Get list of scheduled timers."""
    adapter = _get_adapter(device_id)
    return await adapter.get_timers()


@router.post("/timers", response_model=TimerResponse, dependencies=[Depends(verify_auth)])
async def add_timer(timer: TimerCreate, device_id: int = 0):
    """Create a new timer."""
    adapter = _get_adapter(device_id)
    timer_obj = Timer(**timer.model_dump())
    return await adapter.add_timer(timer_obj)


@router.delete("/timers", response_model=TimerResponse, dependencies=[Depends(verify_auth)])
async def delete_timer(
    service_ref: str,
    begin_time: str,
    end_time: str,
    device_id: int = 0,
):
    """Delete a scheduled timer."""
    adapter = _get_adapter(device_id)
    return await adapter.delete_timer(service_ref, begin_time, end_time)


# ──── Power ────

@router.post("/power", response_model=APIResponse, dependencies=[Depends(verify_auth)])
async def set_power(cmd: PowerCommand, device_id: int = 0):
    """Control STB power state."""
    adapter = _get_adapter(device_id)
    result = await adapter.set_power_state(cmd.action)

    if result:
        status = await adapter.get_status()
        await ws_manager.broadcast_status(status.model_dump())

    return APIResponse(result=result, message=f"Power action '{cmd.action}' executed")


# ──── Stream ────

@router.get("/stream/url", dependencies=[Depends(verify_auth)])
async def get_stream_url(
    service_ref: str = Query(...),
    device_id: int = 0,
):
    """Get streaming URL for a channel."""
    adapter = _get_adapter(device_id)
    url = await adapter.get_stream_url(service_ref)
    if url is None:
        raise HTTPException(status_code=501, detail="Streaming not supported by this adapter")
    return {"url": url, "service_ref": service_ref}


# ──── Network Scan & Connection Management ────

class ConnectRequest(BaseModel):
    host: str
    port: int = 20000


async def _probe_gmscreen(host: str, port: int, timeout: float = 2.0) -> Optional[dict]:
    """Probe a G-MScreen device: TCP connect + quick handshake to get serial/model."""
    import zlib
    XML_HEADER = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"

    def _build(xml_body: str) -> bytes:
        full_xml = f"{XML_HEADER}{xml_body}"
        length_str = str(len(full_xml)).zfill(7)
        return f"Start{length_str}End{full_xml}".encode('utf-8')

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
    except Exception:
        return None

    info = {"host": host, "port": port, "name": "", "serial": "", "version": ""}
    try:
        # req=998 registration
        reg_xml = (
            '<Command request="998"><parm>'
            '<DeviceName>STBScan</DeviceName>'
            '<DeviceModel>Scanner</DeviceModel>'
            '<UUID>stb-scan-probe</UUID>'
            '</parm></Command>'
        )
        writer.write(_build(reg_xml))
        await writer.drain()
        await asyncio.wait_for(reader.read(256), timeout=2.0)

        # Send req=15 to get device info (skip intermediate handshake steps)
        writer.write(_build('<Command request="15" />'))
        await writer.drain()
        header = await asyncio.wait_for(reader.readexactly(16), timeout=2.0)
        if header.startswith(b'GCDH'):
            payload_len = int.from_bytes(header[4:8], byteorder='little')
            payload = await asyncio.wait_for(reader.readexactly(payload_len), timeout=2.0)
            if payload.startswith((b'\x78\x9c', b'\x78\xda', b'\x78\x01')):
                try:
                    payload = zlib.decompress(payload)
                except Exception:
                    pass
            text = payload.decode('utf-8', errors='ignore')
            import xml.etree.ElementTree as ET
            root = ET.fromstring(text)
            info["name"] = root.findtext('.//ProductName', '')
            info["serial"] = root.findtext('.//SerialNumber', '')
            info["version"] = root.findtext('.//SoftwareVersion', '')
    except Exception:
        pass

    try:
        writer.close()
        await asyncio.wait_for(writer.wait_closed(), timeout=0.5)
    except Exception:
        pass

    return info


@router.get("/network/scan", dependencies=[Depends(verify_auth)])
async def network_scan(
    subnet: Optional[str] = Query(None, description="Subnet prefix, e.g. 192.168.50"),
    port: int = Query(20000, description="Port to scan"),
):
    """Scan the local network for G-MScreen devices on the given port."""
    import socket

    # Determine subnet from our own IP if not provided
    if not subnet:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            subnet = ".".join(local_ip.split(".")[:3])
        except Exception:
            subnet = "192.168.1"

    log.info("network_scan_start", subnet=subnet, port=port)

    # Get currently connected adapter to skip its IP during probe
    current_adapter = get_default_adapter()
    current_host = current_adapter.host if current_adapter and current_adapter.is_connected else None

    # Scan all IPs in the subnet concurrently (limited to 50 at a time)
    sem = asyncio.Semaphore(50)

    async def probe_with_sem(ip):
        async with sem:
            return await _probe_gmscreen(ip, port)

    tasks = []
    for i in range(1, 255):
        ip = f"{subnet}.{i}"
        if ip == current_host:
            continue  # Skip currently connected STB (probe would kill connection)
        tasks.append(probe_with_sem(ip))

    results = await asyncio.gather(*tasks)
    found = [r for r in results if r is not None]

    # Add currently connected device info at the top
    if current_host and current_adapter:
        from backend.adapters.gmscreen import GMScreenAdapter
        info = {"host": current_host, "port": port, "name": "", "serial": "", "version": "", "connected": True}
        if isinstance(current_adapter, GMScreenAdapter):
            info["name"] = current_adapter.product_name
            info["serial"] = current_adapter.serial_number
            info["version"] = current_adapter.software_version
        found.insert(0, info)

    log.info("network_scan_done", found=len(found))
    return {"subnet": subnet, "port": port, "devices": found}


@router.post("/device/configure", dependencies=[Depends(verify_auth)])
async def configure_device(req: ConnectRequest, device_id: int = 0):
    """Change the connection target (host/port) and reconnect."""
    # Disconnect existing adapter if any
    existing = get_default_adapter() if device_id == 0 else get_adapter(device_id)
    if existing:
        await existing.disconnect()

    # Create new adapter with the given host/port
    device_config = DeviceConfig(
        name=f"Qviart ({req.host})",
        host=req.host,
        port=req.port,
        adapter="gmscreen",
    )
    adapter = create_adapter(device_config, device_id=device_id)
    connected = await adapter.connect()

    if connected:
        try:
            await adapter.get_channels()
        except Exception:
            pass

    return {
        "connected": connected,
        "host": req.host,
        "port": req.port,
    }


@router.get("/device/connection", dependencies=[Depends(verify_auth)])
async def get_connection_info(device_id: int = 0):
    """Get current connection info."""
    adapter = get_default_adapter() if device_id == 0 else get_adapter(device_id)
    if not adapter:
        return {"configured": False}
    info = {
        "configured": True,
        "host": adapter.host,
        "port": adapter.port,
        "connected": adapter.is_connected,
    }
    from backend.adapters.gmscreen import GMScreenAdapter
    if isinstance(adapter, GMScreenAdapter):
        info["name"] = adapter.product_name
        info["serial"] = adapter.serial_number
        info["version"] = adapter.software_version
    return info
