import atexit
from typing import Sequence, Any, Callable

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.types import Command
from psycopg_pool import ConnectionPool

from llm.deepseek import LLM
from mcp_client.langchain_mcp_client import YourMcpClient
from my_langgraph.graph_state import YourAgentState
from my_langgraph.state_graph import compileGraph


class AgentConfig:
    """
    agent config
    """
    def __init__(self, postgresqlUrl: str, tools: list,  mcpServiceConfig: dict):
        self.postgresqlUrl = postgresqlUrl
        self.tools = []
        self.mcpServiceConfig = mcpServiceConfig
        if tools is not None:
            self.tools = tools
        if mcpServiceConfig is not None:
            remoteTools = YourMcpClient(mcpServiceConfig).getTools()
            self.tools = self.tools + remoteTools
        self.toolsByName = {tool.name: tool for tool in self.tools}
        self.model = LLM(tools=self.tools)

class YourAgent:
    def __init__(self, config: AgentConfig):
        """
        init agent
        """
        self.config = config
        self.connectionPool = ConnectionPool(conninfo=self.config.postgresqlUrl, max_size=10)
        self.stateGraph = compileGraph(self.connectionPool)
        self.sessionId = ""

    def run(self, sessionId: str):
        # 服务结束前优雅关闭agent
        def cleanUp():
            # 关闭agent
            self.__close()

        atexit.register(cleanUp)
        while True:
            # 运行agent
            try:
                self.__run(sessionId=sessionId)
            except KeyboardInterrupt:
                print("\n【agent】正在停止运行...")
                break

    def __run(self, sessionId:str) -> str:
        """
        run agent
        """
        self.sessionId = sessionId
        config = RunnableConfig(configurable={
            "thread_id": sessionId,
            "user_config": self.config,
        })
        # 上次执行结束如果是异常结束，此次重新执行异常节点（重放），如果是正常结束，则重更新执行
        errEnd = self.__checkIfErrEnd(config)
        initState = None
        if errEnd:
            config = self.__getLastestNodeConfig(config)
            config["configurable"]["user_config"] = self.config
        else:
            initState = YourAgentState(intputStr="", outPutStr="")
        result = self.stateGraph.invoke(initState, config=config)
        while "__interrupt__" in result:
            interruptObj = result["__interrupt__"][0]
            approveResult = interruptObj.value
            userActionFlag = input(f'{approveResult}')
            print(f'【You】：{userActionFlag}')
            result = self.__resume(resumeResult=userActionFlag)
        return result["outPutStr"]

    def __resume(self, resumeResult:str):
        """
        resume agent ,it is a private method
        """
        config = RunnableConfig(configurable={
            "thread_id": self.sessionId,
            "user_config": self.config,
        })
        result = self.stateGraph.invoke(Command(resume=resumeResult), config=config)
        return result

    def __checkIfErrEnd(self, config: RunnableConfig) -> bool:
        """
        检查当前会话上一次执行是否是因为崩溃结束
        """
        if self.__isNewSession(config):
            return False
        state = self.stateGraph.get_state(config)
        if not state.next:
            # next 为空，可能是正常结束，也可能是崩溃
            for task in state.tasks:
                if task.error:
                    return True
            return False

        return True

    def __isNewSession(self, config: RunnableConfig):
        """
        判断是否是新的会话
        """
        checkpoint_tuple = self.stateGraph.checkpointer.get_tuple(config=config)
        return checkpoint_tuple is None

    def __getLastestNodeConfig(self, config: RunnableConfig) -> RunnableConfig:
        history = list(self.stateGraph.get_state_history(config))
        prev = history[1]
        return prev.config

    def __close(self):
        """
        close agent
        """
        self.connectionPool.close()


