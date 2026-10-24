import asyncio
import atexit
import json
from sys import prefix
from typing import Sequence, Any, Callable, AsyncGenerator
from unittest import result

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

    async def webStreamRun(self, sessionId: str, opType: str, userMsg: str | None = "") -> AsyncGenerator[dict, None]:
        """
        流式执行 Agent，产出前端事件字典（v3 投影模式）。
        """
        config = RunnableConfig(configurable={
            "thread_id": sessionId,
            "user_config": self.config,
        })

        try:
            if opType == "interrupt":
                input_data = Command(resume=userMsg)
            else:
                errEnd = self.__checkIfErrEnd(config)
                if errEnd:
                    config = self.__getLastestNodeConfig(config)
                    config["configurable"]["user_config"] = self.config
                    input_data = None
                else:
                    input_data = YourAgentState(intputStr=userMsg, outPutStr="")

            # 关键：v3 返回 run 对象，直接消费投影
            stream = self.stateGraph.stream_events(input_data, config=config, version="v3")

            # 1. 消费 LLM 消息流（token、工具调用参数）
            for message in stream.messages:
                # 节点名标签
                if getattr(message, "node", None) == "sys_in_node":
                    continue
                if getattr(message, "node", None):
                    yield {"type": "node", "name": message.node}

                # 流式 token
                for delta in message.text:
                    yield {"type": "token", "content": delta}

                # 模型生成的工具调用参数（可选推给前端）
                finalized_calls = message.tool_calls.get()
                if finalized_calls:
                    for call in finalized_calls:
                        yield {
                            "type": "tool_start",
                            "name": call.get("name"),
                            "input": call.get("args"),
                        }

            # 2. 驱动到完成，拿最终状态（也可以直接 stream.output）
            final_state = stream.output

            # 3. 检查中断（v3 用 stream.interrupted / stream.interrupts）
            if stream.interrupted:
                for intr in stream.interrupts:
                    yield {
                        "type": "interrupt",
                        "value": intr.value,
                        "id": getattr(intr, "id", None) or "1",
                    }

            yield {"type": "done"}

        except Exception as e:
            yield {"type": "error", "message": str(e)}

    def webRun(self, sessionId: str, opType: str, userMsg: str | None = "") -> dict:
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
        result: dict
        if opType == "interrupt":
            result = self.__resume(sessionId= sessionId, resumeResult=userMsg)
        else:
            result = self.stateGraph.invoke(initState, config=config)
        if "__interrupt__" in result:
            interruptObj = result["__interrupt__"][0]
            interruptMsg = interruptObj.value
            return {"type":"interrupt","role":"system", "opType":"interrupt", "content": interruptMsg}

        agentOutput = result["outPutStr"]
        return {"type":"message", "role":"agent", "opType":"message", "content": agentOutput}

    def webHistory(self, sessionId: str):
        config = RunnableConfig(configurable={
            "thread_id": sessionId,
            "user_config": self.config,
        })
        # return self.__getStateHistory(config)
        finalState = self.stateGraph.get_state(config)
        messages = finalState.values["messages"]
        return self.__formatMessages(messages)

    def __formatMessages(self, messages: list) -> list:
        res = []
        for message in messages:
            msgType = message.type
            content = message.content
            if msgType == "human":
                res.append({"role": msgType, "content": content})
            elif msgType == "ai":
                if len(message.tool_calls) > 0:
                    tool_calls = message.tool_calls
                    res.append({"role": msgType, "content": content, "tool_calls": tool_calls})
                else:
                    res.append({"role": msgType, "content": content})
            elif msgType == "tool":
                res.append({"role": msgType, "content": content})
        return res

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
                self.__streamRun(sessionId=sessionId, userMsg=userMsg)
                userMsg = ""
            except KeyboardInterrupt:
                print("\n【Agent】正在停止运行...")
                break

    def singleStreamRun(self, sessionId:str, userMsg:str|None = "") -> str:
        # 服务结束前优雅关闭agent
        def cleanUp():
            # 关闭agent
            self.__close()
        atexit.register(cleanUp)
        return self.__streamRun(sessionId=sessionId, userMsg=userMsg)

    def __streamRun(self, sessionId:str, userMsg: str | None = "") -> str:
        """
        run agent by stream
        """
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
            result = self.__resume(sessionId=sessionId, resumeResult=userActionFlag)

        agentOutput = result["outPutStr"]
        print(f'【Agent】:\n{agentOutput}')
        return agentOutput

    def __resume(self, sessionId:str, resumeResult:str):
        """
        resume agent ,it is a private method
        """
        config = RunnableConfig(configurable={
            "thread_id": sessionId,
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
        history = list(self.__getStateHistory(config))
        prev = history[1]
        return prev.config

    def __getStateHistory(self, config: RunnableConfig):
       return list(self.stateGraph.get_state_history(config))

    def close(self):
        """
        close agent
        """
        self.__close()

    def __close(self):
        """
        close agent
        """
        self.connectionPool.close()


