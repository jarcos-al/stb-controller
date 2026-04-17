"""
SQLite database initialization and access.
Uses aiosqlite for async operations.
"""

import aiosqlite
from pathlib import Path
from typing import Optional

from backend.core.config import get_config
from backend.core.logging import get_logger

log = get_logger("database")

_db: Optional[aiosqlite.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS stb_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 80,
    adapter_type TEXT NOT NULL DEFAULT 'mock',
    credentials TEXT DEFAULT '{}',
    options TEXT DEFAULT '{}',
    status TEXT DEFAULT 'unknown',
    last_seen TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bouquets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stb_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    service_ref TEXT,
    position INTEGER DEFAULT 0,
    FOREIGN KEY (stb_id) REFERENCES stb_devices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stb_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    service_ref TEXT NOT NULL,
    provider TEXT DEFAULT '',
    is_hd INTEGER DEFAULT 0,
    is_favorite INTEGER DEFAULT 0,
    channel_number INTEGER DEFAULT 0,
    FOREIGN KEY (stb_id) REFERENCES stb_devices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bouquet_channels (
    bouquet_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    position INTEGER DEFAULT 0,
    PRIMARY KEY (bouquet_id, channel_id),
    FOREIGN KEY (bouquet_id) REFERENCES bouquets(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS timers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stb_id INTEGER NOT NULL,
    service_ref TEXT,
    channel_name TEXT DEFAULT '',
    begin_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    state INTEGER DEFAULT 0,
    repeated INTEGER DEFAULT 0,
    repeated_days TEXT DEFAULT '',
    FOREIGN KEY (stb_id) REFERENCES stb_devices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS epg_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_ref TEXT NOT NULL,
    event_id INTEGER,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    description_ext TEXT DEFAULT '',
    start_time TEXT NOT NULL,
    duration INTEGER DEFAULT 0,
    genre TEXT DEFAULT '',
    cached_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_epg_cache_service ON epg_cache(service_ref);
CREATE INDEX IF NOT EXISTS idx_epg_cache_time ON epg_cache(start_time);
CREATE INDEX IF NOT EXISTS idx_channels_stb ON channels(stb_id);
CREATE INDEX IF NOT EXISTS idx_bouquets_stb ON bouquets(stb_id);

CREATE TABLE IF NOT EXISTS user_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,
    position INTEGER DEFAULT 0,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


async def get_db() -> aiosqlite.Connection:
    """Get the database connection, creating it if necessary."""
    global _db
    if _db is None:
        config = get_config()
        db_path = Path(config.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        _db = await aiosqlite.connect(str(db_path))
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await _db.executescript(SCHEMA)
        await _db.commit()
        log.info("database_initialized", path=str(db_path))

    return _db


async def close_db():
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        log.info("database_closed")
