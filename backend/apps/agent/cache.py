import hashlib
import json
from pathlib import Path
from typing import Any

from django.conf import settings


CACHE_VERSION = "v1"


def message_cache_key(message: str) -> str:
    normalized = " ".join(message.strip().lower().split())
    return hashlib.sha256(f"{CACHE_VERSION}:{normalized}".encode("utf-8")).hexdigest()


def load_parsed_request(message: str) -> dict[str, Any] | None:
    path = _cache_path(message)
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    parsed = payload.get("parsed_request")
    return parsed if isinstance(parsed, dict) else None


def save_parsed_request(message: str, parsed_request: dict[str, Any]) -> None:
    path = _cache_path(message)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "cache_version": CACHE_VERSION,
                "message_hash": message_cache_key(message),
                "parsed_request": parsed_request,
            },
            handle,
            indent=2,
            sort_keys=True,
        )


def _cache_path(message: str) -> Path:
    return Path(settings.PARSED_REQUEST_CACHE_DIR) / f"{message_cache_key(message)}.json"
