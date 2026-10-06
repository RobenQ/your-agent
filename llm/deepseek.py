from typing import Sequence, Any, Callable

from dotenv import load_dotenv

from langchain_core.tools import BaseTool
from langchain_deepseek import ChatDeepSeek

class LLM:
    def __init__(self, tools: list):
        load_dotenv()
        # 初始换大模型，这里使用deep_seek llm，注意：需要在环境变量中设置api key
        llm = ChatDeepSeek(
            model="deepseek-v4-flash",
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            extra_body={"thinking": {"type": "disabled"}}
        )
        self.llm = llm
        self.llmWithTools = self.llm.bind_tools(tools)

# 绑定工具
# llm_with_tools = llm.bind_tools(tools)