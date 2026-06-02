from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


SERVER_ROOT = Path(__file__).resolve().parents[1]


def cache_root() -> Path:
    configured = os.getenv("MCP_CACHE_DIR")
    if not configured:
        return SERVER_ROOT / "cache"

    path = Path(configured)
    if path.is_absolute():
        return path

    if path.parts and path.parts[0] == SERVER_ROOT.name:
        return SERVER_ROOT.parent / path

    return SERVER_ROOT / path


def cache_dir(name: str) -> Path:
    path = cache_root() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_key(*parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
