from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.memory import InMemoryStore
from psycopg_pool import ConnectionPool

from my_langgraph.graph_edgeRouter import tool_continue
from my_langgraph.graph_nodes import sys_in_node, llm_node, tool_node, sys_out_node
from my_langgraph.graph_state import YourAgentState


def compileGraph(connectionPool:ConnectionPool) -> CompiledStateGraph[Any, Any, Any, Any]:
    graph = StateGraph(YourAgentState)

    graph.add_node("sys_in_node", sys_in_node)
    graph.add_node("llm_node", llm_node)
    graph.add_node("tool_node", tool_node)
    graph.add_node("sys_out_node", sys_out_node)

    graph.add_edge(START, "sys_in_node")
    graph.add_edge("sys_in_node", "llm_node")
    graph.add_conditional_edges("llm_node", tool_continue, ["tool_node", "sys_out_node"])
    graph.add_edge("tool_node", "llm_node")
    graph.add_edge("sys_out_node", END)

    # 持久化机制
    # 内存持久化
    # checkPointSaver = InMemorySaver()
    # postgreSql持久化
    # DB_URI = "postgresql://postgres:123456@localhost:5432/my_langgraph?sslmode=disable"

    checkpointer = PostgresSaver(connectionPool)
    # checkpointer.setup()  # 首次运行建表，之后可省略
    store = InMemoryStore()
    graph = graph.compile(checkpointer=checkpointer, store=store)
    return graph