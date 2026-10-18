Your-Agent 的核心模块，包含agent sdk和agent server。
agent server集成了agent sdk，并暴露处理http接口（目前只支持http，SSE协议待适配）。

配合Your-MCP-Server、Your-Agent-ui使用，可快速实现一个支持tool call、工具调用审批、skill的chat agent。
