from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

ollamaLLM = ChatOllama(
    model="qwen3.8:27b-mlx",          # 换成你本地已有的模型名
    base_url="http://127.0.0.1:9091",  # 默认值，可省略
    # temperature=0,
    reasoning= "medium",
)

# ollamaLLM = ChatOpenAI(
#     model="qwen3.5:4b",
#     base_url="http://localhost:11434/v1",  # 关键：指向 /v1
#     api_key="ollama",  # 随意填，Ollama 不校验
#     extra_body={
#             "reasoning_effort": "low"  # 或 "low" / "high" / "none"
#         }
# )