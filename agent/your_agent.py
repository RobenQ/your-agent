import asyncio
import atexit
import json
from sys import prefix
from typing import Sequence, Any, Callable

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_skillkit import SkillKit
from langgraph.types import Command
from orjson import orjson
from psycopg_pool import ConnectionPool

from llm.deepseek import LLM
from mcp_client.langchain_mcp_client import YourMcpClient
from my_langgraph.graph_state import YourAgentState
from my_langgraph.state_graph import compileGraph

__defaultSkillDir__ = "./skill"

class AgentConfig:
    """
    agent config
    """
    def __init__(self, postgresqlUrl: str|None = None,
                 localTools: list|None = None,
                 mcpServiceConfig: dict| None = None,
                 autoApprove: bool|None = False,
                 skillPath: str|None = None):
        self.postgresqlUrl = postgresqlUrl
        self.localTools = localTools
        self.mcpServiceConfig = mcpServiceConfig
        self.mcpTools = []
        self.autoApprove = autoApprove

        if skillPath is None or skillPath == "":
            skillPath = __defaultSkillDir__
        self.skillPath = skillPath

        self.tools = []
        self.mcpClient = None
        self.skillKit = None
        self.skillTools = []
        self.toolsByName = dict
        self.model = None

    def Init(self):
        if self.localTools is not None:
            self.tools = self.tools + self.localTools

        if self.mcpServiceConfig is not None:
            self.mcpClient = YourMcpClient(self.mcpServiceConfig)
            self.mcpTools = self.mcpClient.getTools()
            self.tools = self.tools +  self.mcpTools

        self.skillKit = SkillKit(self.skillPath)
        self.skillTools = self.skillKit.tools
        if self.skillTools is not None:
            self.tools = self.tools + self.skillTools
        self.toolsByName = {tool.name: tool for tool in self.tools}
        self.model = LLM(tools=self.tools)
        return self


class YourAgent:
    def __init__(self, config: AgentConfig):
        """
        init agent
        """
        self.config = config
        self.connectionPool = ConnectionPool(conninfo=self.config.postgresqlUrl, max_size=10)
        self.stateGraph = compileGraph(self.connectionPool)
        self.sessionId = ""
    def streamingRun(self):
        # 服务结束前优雅关闭agent
        def cleanUp():
            # 关闭agent
            self.__close()

        atexit.register(cleanUp)

    def cliStreamRun(self, sessionId:str, userMsg:str|None = ""):
        # 服务结束前优雅关闭agent
        def cleanUp():
            # 关闭agent
            self.__close()

        atexit.register(cleanUp)
        while True:
            # 运行agent
            try:
                self.__stream_run(sessionId=sessionId, userMsg=userMsg)
                userMsg = ""
            except KeyboardInterrupt:
                print("\n【Agent】正在停止运行...")
                break

    def singleStreamRun(self, sessionId:str, userMsg:str|None = ""):
        # 服务结束前优雅关闭agent
        def cleanUp():
            # 关闭agent
            self.__close()

        atexit.register(cleanUp)
        self.__stream_run(sessionId=sessionId, userMsg=userMsg)

    def __stream_run(self, sessionId:str, userMsg: str | None = "") -> str:
        """
        run agent by stream
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
            initState = YourAgentState(intputStr=userMsg, outPutStr="")

        events = self.stateGraph.stream_events(initState, config=config, version="v3")
        for message in events.messages:
            if message.node != "llm_node":
                continue
            print("【Agent】")
            print(message.text, end="\n", flush=True)
        while events.interrupted:
            approveResult = input(f'【Agent】\n{events.interrupts[0].value}')
            events = self.stateGraph.stream_events(Command(resume=approveResult), config=config, version="v3")
            # print("【Agent】", end="\n", flush=True)
            for message in events.messages:
                if message.node != "llm_node" :
                    continue
                print("【Agent】")
                print(message.text, end="\n", flush=True)

        agentOutput = events.output["outPutStr"][-1]["text"]
        # print(f'【Agent】:\n{agentOutput}')
        return agentOutput

    def cliRun(self, sessionId: str, userMsg:str|None = ""):
        # 服务结束前优雅关闭agent
        def cleanUp():
            # 关闭agent
            self.__close()

        atexit.register(cleanUp)
        while True:
            # 运行agent
            try:
                self.__run(sessionId=sessionId, userMsg=userMsg)
                userMsg = ""
            except KeyboardInterrupt:
                print("\n【Agent】正在停止运行...")
                break

    def singleRun(self, sessionId: str, userMsg:str|None = "") -> str:
        # 服务结束前优雅关闭agent
        def cleanUp():
            # 关闭agent
            self.__close()

        atexit.register(cleanUp)
        return self.__run(sessionId=sessionId, userMsg=userMsg)

    def __run(self, sessionId:str, userMsg:str|None = "") -> str:
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
            initState = YourAgentState(intputStr=userMsg, outPutStr="")
        result = self.stateGraph.invoke(initState, config=config)
        while "__interrupt__" in result:
            interruptObj = result["__interrupt__"][0]
            approveResult = interruptObj.value
            userActionFlag = input(f'{approveResult}')
            # print(f'【You】：{userActionFlag}')
            result = self.__resume(resumeResult=userActionFlag)

        agentOutput = result["outPutStr"]
        print(f'【Agent】:\n{agentOutput}')
        return agentOutput

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

        return True and state.next[0] != "sys_in_node"

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


