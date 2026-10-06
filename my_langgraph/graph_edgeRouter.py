from typing import Literal

from langgraph.graph import MessagesState



def tool_continue(state: MessagesState) -> Literal["tool_node", "sys_out_node"]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tool_node"

    return "sys_out_node"