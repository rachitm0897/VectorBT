from __future__ import annotations

from typing import Callable

from mcp.server.fastmcp import FastMCP


ToolRegistrar = Callable[[FastMCP], None]


def register_tool_groups(mcp: FastMCP, registrars: list[ToolRegistrar]) -> None:
    for registrar in registrars:
        registrar(mcp)

