from langchain_ollama import ChatOllama

ollamaLLM = ChatOllama(
    model="qwen2.5:7b",          # 换成你本地已有的模型名
    base_url="http://localhost:11434",  # 默认值，可省略
    temperature=0,
)