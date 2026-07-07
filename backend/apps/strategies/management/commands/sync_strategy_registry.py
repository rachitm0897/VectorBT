from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.backtesting.mcp_client import MCPClientError, call_mcp_tool


class Command(BaseCommand):
    help = "Synchronize the canonical strategy registry through the MCP engine."

    def handle(self, *args, **options):
        try:
            result = call_mcp_tool("sync_strategy_registry", {})
        except MCPClientError as exc:
            raise CommandError(f"{exc.code}: {exc}") from exc

        if result.get("status") == "error":
            errors = result.get("errors") if isinstance(result.get("errors"), list) else ["sync_failed"]
            raise CommandError(f"{errors[0]}: {result.get('message') or 'Strategy registry sync failed.'}")

        self.stdout.write(json.dumps(result, indent=2, default=str))
