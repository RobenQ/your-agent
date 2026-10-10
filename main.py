from agent.your_agent import AgentConfig, YourAgent
from tools import tools

if __name__ == '__main__':
    # 初始化agent config
    postgresqlUrl = "postgresql://postgres:123456@localhost:5432/langgraph?sslmode=disable"
    mcpServerConfig = {
        "caculator-mcp-server":{
            "url": "http://localhost:8080/mcp",
            "transport": "streamable_http"
        }
    }
    agentConfig = AgentConfig(postgresqlUrl=postgresqlUrl, tools=tools.custom_tools, mcpServiceConfig=mcpServerConfig)

    # 初始化agent
    yourAgent = YourAgent(agentConfig)
    sessionId = "1419_10"

    # 运行agent
    yourAgent.run(sessionId)
