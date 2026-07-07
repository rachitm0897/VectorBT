from __future__ import annotations

import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from app.logging import configure_logging
from app.registry import register_tool_groups
from app.settings import SERVER_ROOT
from tools.legacy import register_legacy_tools
from tools.public import register_public_tools


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _normalize_path(value: str, default: str) -> str:
    path = (value or default).strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/") or default


def create_mcp_app() -> FastMCP:
    load_dotenv(SERVER_ROOT / ".env")
    load_dotenv()
    configure_logging()

    host = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    port = _env_int("MCP_SERVER_PORT", _env_int("PORT", 8001))
    base_path = _normalize_path(os.getenv("MCP_BASE_PATH", "/mcp"), "/mcp")
    sse_path = _normalize_path(os.getenv("MCP_SSE_PATH", "/sse"), "/sse")

    mcp = FastMCP(
        "VectorBT Quant Research MCP",
        host=host,
        port=port,
        streamable_http_path=base_path,
        sse_path=sse_path,
    )
    register_tool_groups(mcp, [register_public_tools, register_legacy_tools])
    return mcp
