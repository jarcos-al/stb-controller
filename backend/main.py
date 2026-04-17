"""
STB Control Panel — Main FastAPI Application

Self-hosted web UI for controlling satellite/STB decoders.
Inspired by G-MScreen, built for homelab deployment.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.core.config import get_config, load_config
from backend.core.logging import setup_logging, get_logger
from backend.core.database import get_db, close_db
from backend.core.websocket import ws_manager
from backend.adapters.registry import create_adapter, disconnect_all, get_default_adapter
from backend.api.routes import router as api_router


# ──── Lifespan ────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    config = get_config()

    # Setup logging
    setup_logging(config.logging.level, config.logging.format)
    log = get_logger("main")
    log.info("starting", name=config.name)

    # Initialize database
    await get_db()

    # Create adapters for configured devices
    for i, device in enumerate(config.devices):
        adapter = create_adapter(device, device_id=i)
        try:
            connected = await adapter.connect()
            log.info("device_initialized",
                     name=device.name,
                     adapter=device.adapter,
                     connected=connected)
        except Exception as e:
            log.error("device_init_failed", name=device.name, error=str(e))

    # Start background status polling
    status_task = asyncio.create_task(_poll_status(config.cache.status_poll))

    # Pre-load channels to populate the name cache for status display
    adapter = get_default_adapter()
    if adapter and adapter.is_connected:
        try:
            await adapter.get_channels()
        except Exception as e:
            log.error("channels_preload_failed", error=str(e))

    log.info("started", devices=len(config.devices))

    yield

    # Shutdown
    log.info("shutting_down")
    status_task.cancel()
    try:
        await status_task
    except asyncio.CancelledError:
        pass
    await disconnect_all()
    await close_db()
    log.info("shutdown_complete")


async def _poll_status(interval: int):
    """Background task to poll STB status and broadcast to WebSocket clients."""
    log = get_logger("status_poller")
    while True:
        try:
            await asyncio.sleep(interval)
            adapter = get_default_adapter()
            if adapter and ws_manager.client_count > 0:
                if adapter.is_connected:
                    status = await adapter.get_status()
                    data = status.model_dump()
                    data['stb_connected'] = True
                    await ws_manager.broadcast_status(data)
                else:
                    await ws_manager.broadcast_status({'stb_connected': False})
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("status_poll_failed", error=str(e))
            await asyncio.sleep(interval)


# ──── App Factory ────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = load_config()
    # Re-setup logging early
    setup_logging(config.logging.level, config.logging.format)

    app = FastAPI(
        title="STB Control Panel",
        description="Self-hosted web UI for STB/satellite decoder control",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production via reverse proxy
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(api_router)

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    await _handle_ws_message(message, websocket)
                except json.JSONDecodeError:
                    await ws_manager.send_personal(websocket, {
                        "type": "error",
                        "data": {"message": "Invalid JSON"},
                    })
        except (WebSocketDisconnect, RuntimeError):
            ws_manager.disconnect(websocket)

    # Static files (built frontend)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        # Serve SvelteKit build
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets") if (static_dir / "assets").exists() else str(static_dir)), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """Serve the SvelteKit SPA for all non-API routes."""
            # Try to serve the exact file first
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            # Fall back to index.html for SPA routing
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return {"message": "Frontend not built yet. Access API at /api/docs"}
    else:
        @app.get("/")
        async def root():
            return {
                "message": "STB Control Panel API",
                "docs": "/api/docs",
                "version": "0.1.0",
            }

    return app


async def _handle_ws_message(message: dict, websocket: WebSocket):
    """Handle incoming WebSocket messages from clients."""
    log = get_logger("ws_handler")
    msg_type = message.get("type", "")

    if msg_type == "keypress":
        key = message.get("data", {}).get("key", "")
        key_type = message.get("data", {}).get("key_type", "short")
        adapter = get_default_adapter()
        if adapter:
            result = await adapter.send_key(key, key_type)
            await ws_manager.send_personal(websocket, {
                "type": "keypress_result",
                "data": result.model_dump(),
            })
            # Broadcast updated status
            if result.result:
                try:
                    status = await adapter.get_status()
                    await ws_manager.broadcast_status(status.model_dump())
                except Exception:
                    pass

    elif msg_type == "get_status":
        adapter = get_default_adapter()
        if adapter:
            status = await adapter.get_status()
            await ws_manager.send_personal(websocket, {
                "type": "status_update",
                "data": status.model_dump(),
            })

    elif msg_type == "heartbeat":
        await ws_manager.send_personal(websocket, {
            "type": "heartbeat",
            "data": {},
        })

    else:
        log.debug("ws_unknown_message", type=msg_type)


# Create the app instance
app = create_app()
