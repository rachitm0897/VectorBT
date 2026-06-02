from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import threading
import time
from datetime import timedelta
from typing import Any, Callable, Coroutine, TypeVar

from django.conf import settings
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from apps.agent.mcp_client.errors import (
    MCPClientError,
    MCPServerUnavailableError,
    MCPToolError,
)


logger = logging.getLogger(__name__)
T = TypeVar("T")


async def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    timeout_seconds = float(settings.MCP_CALL_TIMEOUT_SECONDS)
    started = time.perf_counter()
    try:
        return await asyncio.wait_for(
            _call_mcp_tool_once(tool_name, arguments, timeout_seconds),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        logger.warning("MCP call timed out tool=%s timeout=%s", tool_name, timeout_seconds)
        raise MCPServerUnavailableError("The MCP strategy server timed out.") from exc
    except MCPClientError:
        raise
    except Exception as exc:
        logger.exception("MCP server unavailable tool=%s", tool_name)
        raise MCPServerUnavailableError("The MCP strategy server is unavailable.") from exc
    finally:
        logger.info("MCP call finished tool=%s runtime=%.3fs", tool_name, time.perf_counter() - started)


def call_mcp_tool_sync(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return _run_async_sync(lambda: call_mcp_tool(tool_name, arguments))


async def list_mcp_tools() -> list[str]:
    timeout_seconds = float(settings.MCP_CALL_TIMEOUT_SECONDS)
    try:
        return await asyncio.wait_for(_list_mcp_tools_once(timeout_seconds), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        raise MCPServerUnavailableError("The MCP strategy server timed out.") from exc
    except MCPClientError:
        raise
    except Exception as exc:
        logger.exception("MCP tool listing failed")
        raise MCPServerUnavailableError("The MCP strategy server is unavailable.") from exc


def list_mcp_tools_sync() -> list[str]:
    return _run_async_sync(list_mcp_tools)


async def _call_mcp_tool_once(
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    params = _server_parameters()
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(
            read_stream,
            write_stream,
            read_timeout_seconds=timedelta(seconds=timeout_seconds),
        ) as session:
            await session.initialize()
            tools = await _tool_names(session)
            if tool_name not in tools:
                raise MCPToolError(f"MCP tool '{tool_name}' is not available.", "mcp_tool_unavailable")

            result = await session.call_tool(
                tool_name,
                arguments,
                read_timeout_seconds=timedelta(seconds=timeout_seconds),
            )
            if result.isError:
                raise MCPToolError(_safe_result_message(result), "mcp_tool_failed")
            return _parse_tool_result(result)


async def _list_mcp_tools_once(timeout_seconds: float) -> list[str]:
    params = _server_parameters()
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(
            read_stream,
            write_stream,
            read_timeout_seconds=timedelta(seconds=timeout_seconds),
        ) as session:
            await session.initialize()
            return await _tool_names(session)


async def _tool_names(session: ClientSession) -> list[str]:
    tools_result = await session.list_tools()
    return [tool.name for tool in tools_result.tools]


def _parse_tool_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured

    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}

    return {"status": "success", "content": [_content_item(item) for item in result.content]}


def _safe_result_message(result: Any) -> str:
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            return text[:500]
    return "The MCP tool returned an error."


def _content_item(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "dict"):
        return item.dict()
    return {"type": getattr(item, "type", "unknown"), "text": getattr(item, "text", "")}


def _server_parameters() -> StdioServerParameters:
    return StdioServerParameters(
        command=str(settings.MCP_SERVER_COMMAND),
        args=_split_args(settings.MCP_SERVER_ARGS),
        env=None,
        cwd=str(settings.BASE_DIR.parent),
    )


def _split_args(raw_args: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(raw_args, (list, tuple)):
        return [str(item) for item in raw_args]
    raw_args = str(raw_args or "").strip()
    if not raw_args:
        return []

    parts = shlex.split(raw_args, posix=os.name != "nt")
    return [part.strip().strip('"').strip("'") for part in parts]


def _run_async_sync(factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())

    result: dict[str, T] = {}
    errors: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(factory())
        except BaseException as exc:
            errors["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if errors:
        raise errors["error"]
    return result["value"]
