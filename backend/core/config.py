"""
Application configuration management.
Loads from YAML config file with environment variable overrides.
"""

import os
import yaml
import re
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "/config"))
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))


class AuthConfig(BaseModel):
    enabled: bool = True
    method: str = "basic"  # basic | jwt
    username: str = "admin"
    password_hash: str = ""


class DeviceConfig(BaseModel):
    name: str
    host: str
    port: int = 80
    adapter: str = "mock"  # enigma2 | gmscreen | adb | ir_broadlink | mock
    credentials: dict = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)


class CacheConfig(BaseModel):
    epg_ttl: int = 300
    channels_ttl: int = 3600
    status_poll: int = 5


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"


class AppConfig(BaseModel):
    name: str = "STB Control Panel"
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    secret_key: str = "change-me-in-production"
    auth: AuthConfig = Field(default_factory=AuthConfig)
    devices: list[DeviceConfig] = Field(default_factory=list)
    database_path: str = str(DATA_DIR / "stbcontrol.db")
    cache: CacheConfig = Field(default_factory=CacheConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def _resolve_env_vars(value: str) -> str:
    """Resolve ${ENV_VAR} and ${ENV_VAR:-default} patterns in strings."""
    pattern = r'\$\{([^}]+)\}'

    def replacer(match):
        expr = match.group(1)
        if ":-" in expr:
            var_name, default = expr.split(":-", 1)
            return os.getenv(var_name, default)
        return os.getenv(expr, match.group(0))

    return re.sub(pattern, replacer, value)


def _resolve_env_recursive(data):
    """Recursively resolve environment variables in config data."""
    if isinstance(data, str):
        return _resolve_env_vars(data)
    elif isinstance(data, dict):
        return {k: _resolve_env_recursive(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_resolve_env_recursive(item) for item in data]
    return data


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file with env var resolution."""
    if config_path is None:
        config_path = os.getenv("CONFIG_FILE", str(CONFIG_DIR / "stb-control.yaml"))

    config_file = Path(config_path)

    if config_file.exists():
        with open(config_file, "r") as f:
            raw = yaml.safe_load(f) or {}
        resolved = _resolve_env_recursive(raw)

        # Map YAML structure to flat AppConfig
        app_section = resolved.get("app", {})
        config_data = {
            "name": app_section.get("name", "STB Control Panel"),
            "host": app_section.get("host", "0.0.0.0"),
            "port": app_section.get("port", 8080),
            "debug": app_section.get("debug", False),
            "secret_key": app_section.get("secret_key", "change-me-in-production"),
            "auth": resolved.get("auth", {}),
            "devices": resolved.get("devices", []),
            "database_path": resolved.get("database", {}).get("path", str(DATA_DIR / "stbcontrol.db")),
            "cache": resolved.get("cache", {}),
            "logging": resolved.get("logging", {}),
        }
        return AppConfig(**config_data)
    else:
        # Generate default config with mock device
        default_config = AppConfig(
            devices=[
                DeviceConfig(
                    name="Demo STB (Mock)",
                    host="127.0.0.1",
                    port=0,
                    adapter="mock",
                )
            ]
        )
        return default_config


# Global config instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
