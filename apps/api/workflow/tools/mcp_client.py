"""MCP (Model Context Protocol) client for connecting to internal MCP servers.

All MCP servers are assumed to use Streamable HTTP transport.
"""

import httpx

from apps.api.logging_config import get_logger

logger = get_logger(__name__)


class McpClient:
    """Client for communicating with MCP servers over Streamable HTTP.

    Sends tool invocation requests to MCP-compliant servers and returns
    the structured results. Each agent has its own MCP server URL.
    """

    def __init__(self, server_url: str, timeout: float = 30.0) -> None:
        """Initialize the MCP client with a target server URL.

        Args:
            server_url: The base URL of the MCP server (Streamable HTTP endpoint).
            timeout: Request timeout in seconds.
        """
        self.server_url = server_url
        self.timeout = timeout

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Invoke a tool on the remote MCP server.

        Sends a JSON-RPC style request to the MCP server's Streamable HTTP
        endpoint and returns the parsed result.

        Args:
            tool_name: The name of the tool to invoke on the MCP server.
            arguments: The keyword arguments to pass to the tool.

        Returns:
            The parsed response dictionary from the MCP server.

        Raises:
            McpClientError: If the request fails or the server returns an error.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": 1,
        }

        logger.info(
            "mcp_tool_call",
            server_url=self.server_url,
            tool_name=tool_name,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.server_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()

                if result.get("error"):
                    logger.error(
                        "mcp_tool_error",
                        tool_name=tool_name,
                        error=result["error"],
                    )
                    return {"error": result["error"]}

                logger.info("mcp_tool_success", tool_name=tool_name)
                return result.get("result", {})

        except httpx.HTTPError as error:
            logger.exception(
                "mcp_request_failed",
                server_url=self.server_url,
                tool_name=tool_name,
            )
            return {"error": f"MCP request failed: {error}"}

    async def list_tools(self) -> list[dict]:
        """Retrieve the list of available tools from the MCP server.

        Returns:
            A list of tool definition dictionaries.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.server_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
                return result.get("result", {}).get("tools", [])
        except httpx.HTTPError:
            logger.exception("mcp_list_tools_failed", server_url=self.server_url)
            return []
