class MCPClientError(Exception):
    code = "mcp_client_error"

    def __init__(self, message: str, code: str | None = None):
        self.safe_message = message
        if code:
            self.code = code
        super().__init__(message)


class MCPServerUnavailableError(MCPClientError):
    code = "mcp_server_unavailable"


class MCPToolError(MCPClientError):
    code = "mcp_tool_failed"
