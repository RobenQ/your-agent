from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek

load_dotenv()
 # 初始换大模型，这里使用deep_seek llm，注意：需要在环境变量中设置api key
deepseekLLM = ChatDeepSeek(
    model="deepseek-v4-flash",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    extra_body={"thinking": {"type": "disabled"}}
)