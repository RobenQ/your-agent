from agent.your_agent import AgentConfig, YourAgent
from tools import tools

if __name__ == '__main__':
    # 初始化agent config
    postgresqlUrl = "postgresql://postgres:123456@localhost:5432/langgraph?sslmode=disable"
    agentConfig = AgentConfig(postgresqlUrl=postgresqlUrl, tools=tools.custom_tools)

    # 初始化agent
    yourAgent = YourAgent(agentConfig)
    sessionId = "1419_6"

    # 运行agent
    yourAgent.run(sessionId=sessionId)

    # 关闭postgresql线程池
    yourAgent.close()
