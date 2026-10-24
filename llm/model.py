from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel


class LLM:
    def __init__(self,llmModel:BaseChatModel, tools: list):
        load_dotenv()
        # 初始换大模型，这里使用deep_seek llm，注意：需要在环境变量中设置api key
        llm = llmModel
        self.llm = llm
        self.llmWithTools = self.llm.bind_tools(tools)