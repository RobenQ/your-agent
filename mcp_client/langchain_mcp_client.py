import asyncio
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient


class YourMcpClient:
    def __init__(self, mcpServiceConfig: dict[str, Any]):
        self.mcpClient =  MultiServerMCPClient(mcpServiceConfig, tool_name_prefix=True)

    def getTools(self):
        tools = asyncio.run(self.mcpClient.get_tools())
        return tools