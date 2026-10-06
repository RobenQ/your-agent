from typing import Sequence, Any, Callable

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.types import Command
from psycopg_pool import ConnectionPool

from llm.deepseek import LLM
from my_langgraph.graph_state import YourAgentState
from my_langgraph.state_graph import compileGraph


class AgentConfig:
    """
    agent config
    """
    def __init__(self, postgresqlUrl: str, tools: list):
        self.postgresqlUrl = postgresqlUrl
        self.tools = tools
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

    def run(self, sessionId:str, userInput:str) -> str:
        """
        run agent
        """
        self.sessionId = sessionId
        config = RunnableConfig(configurable={
            "thread_id": sessionId,
            "agent_model": self.config.model,
        })
        result = self.stateGraph.invoke(YourAgentState(intputStr=userInput, outPutStr=""), config=config)
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
            "agent_model": self.config.model,
        })
        result = self.stateGraph.invoke(Command(resume=resumeResult), config=config)
        return result

    def close(self):
        """
        close agent
        """
        self.connectionPool.close()


