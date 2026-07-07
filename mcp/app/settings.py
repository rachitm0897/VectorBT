from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_ROOT.parent


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_path(name: str, default: str | Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser() if value else Path(default)


@dataclass(frozen=True)
class ResearchSettings:
    server_root: Path = SERVER_ROOT
    repo_root: Path = REPO_ROOT
    cache_dir: Path = _env_path("MCP_CACHE_DIR", SERVER_ROOT / "cache")
    stock_strategy_profiling_root: Path = _env_path(
        "STOCK_STRATEGY_PROFILING_ROOT",
        r"D:\Finflock\stock_strategy_profilling",
    )
    strategy_registry_startup_sync: bool = _env_bool("MCP_STRATEGY_REGISTRY_STARTUP_SYNC", False)
    analytics_enabled: bool = _env_bool("ANALYTICS_ENABLED", False)
    analytics_db_name: str = os.getenv("ANALYTICS_DB_NAME", "analytics")
    analytics_db_user: str = os.getenv("ANALYTICS_DB_USER", "analytics_writer")
    analytics_db_password: str = os.getenv("ANALYTICS_DB_PASSWORD", "analytics_writer_password")
    analytics_db_host: str = os.getenv("ANALYTICS_DB_HOST", "localhost")
    analytics_db_port: int = _env_int("ANALYTICS_DB_PORT", 5432)
    engine_version: str = os.getenv("MCP_ENGINE_VERSION", "mcp-first-0.1")


def get_settings() -> ResearchSettings:
    return ResearchSettings()

