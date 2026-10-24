from langchain_core.tools import tool
from langgraph.types import interrupt


# 工具定义
@tool
def multiply(a: int, b: int) -> int:
    """计算 `a` 和 `b` 的乘积.

    Args:
        a: First int
        b: Second int
    """
    return a * b

@tool
def add(a: int, b: int) -> int:
    """Adds `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a + b

@tool
def divide(a: int, b: int) -> float:
    """Divide `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a / b

@tool
def customInterrupt() -> str:
    """
    中断方法，当用户要求审批某些动作时调用
    """
    approveMsg = f'continue？【y/n】：'
    interruptResult = interrupt(approveMsg).lower()
    if interruptResult != "y":
        return "审批不通过"
    return "审批通过"

# 工具集合
custom_tools = [customInterrupt]