from langchain_core.tools import tool

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
# 工具集合
custom_tools = [add, multiply, divide]

# 工具名称的集合
tools_by_name = {tool.name: tool for tool in custom_tools}