import asyncio

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState
from langgraph.types import interrupt

from llm.deepseek import LLM
from my_langgraph.graph_state import YourAgentState


# 系统进入节点，在用户输入前给一个系统消息
def sys_in_node(state: YourAgentState) -> YourAgentState:
    sysMsg = SystemMessage(content="你是一个数字计算小能手")
    interruptResult = interrupt("please enter your input：")
    humanMsg = HumanMessage(content=interruptResult)
    return YourAgentState(messages=[sysMsg] + [humanMsg],intputStr=interruptResult)

# 大模型请求节点
def llm_node(state: YourAgentState, config: RunnableConfig) -> YourAgentState:
    userConfig = config["configurable"]["user_config"]
    llmRes =userConfig.model.llmWithTools.invoke(state["messages"])
    # print(f'llm_node llmRes:{llmRes}')
    return MessagesState(messages=[llmRes])

# 工具执行节点
def tool_node(state: YourAgentState, config: RunnableConfig) -> YourAgentState:
    # print(f'tool_node state:{state}')
    userConfig = config["configurable"]["user_config"]
    last_msg = state["messages"][-1]
    if len(last_msg.tool_calls) == 0 :
        # print("不需要工具调用")
        return state
    tool_names = [call["name"] for call in last_msg.tool_calls]
    interruptResult = interrupt(f'【Agent】:I will call the tool {tool_names} ，continue？【y/n】：')
    toolRes = []
    # print(f'需要调用的工具列表：{last_msg.tool_calls}')
    for call in last_msg.tool_calls:
        toolName = call["name"]
        # print(f'用户审批结果：{interruptResult}')
        if "n" == str(interruptResult).lower():
            toolRes.append(ToolMessage(content="工具调用未授权", tool_call_id=call["id"]))
            continue
        tool = userConfig.toolsByName[toolName]
        observation = asyncio.run(tool.ainvoke(call["args"]))
        print(f'【Agent】:call the tool：{call["name"]}， result：{observation}')
        toolRes.append(ToolMessage(content=observation, tool_call_id=call["id"]))
    return MessagesState(messages=toolRes)

# 系统输出节点
def sys_out_node(state: YourAgentState) -> YourAgentState:
    last_content = state["messages"][-1].content
    print(f'【Agent】：{last_content}')
    endState = YourAgentState(outPutStr=last_content)
    # print(f'end MessagesState：{endState}')
    return endState