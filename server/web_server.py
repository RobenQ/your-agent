import atexit

import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from agent.request import AgentInvokeRequest, ChatRequest, ResumeRequest
from agent.your_agent import AgentConfig, YourAgent
from tools import tools

class ApiServer:
    def __init__(self):
        self.server = FastAPI()
        # 允许跨域（前端不同端口时需要）
        self.server.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        # 初始化agent config
        postgresqlUrl = "postgresql://postgres:123456@localhost:5432/langgraph?sslmode=disable"
        mcpServerConfig = {
            "caculator-mcp-server": {
                "url": "http://localhost:8080/mcp",
                "transport": "streamable_http"
            }
        }
        agentConfig = AgentConfig(postgresqlUrl=postgresqlUrl, localTools=tools.custom_tools,
                                  mcpServiceConfig=mcpServerConfig, autoApprove=False).Init()
        # 初始化agent
        yourAgent = YourAgent(agentConfig)
        self.agentConfig = agentConfig
        self.yourAgent = yourAgent

        # 服务结束前优雅关闭agent
        def cleanUp():
            # 关闭agent
            self.yourAgent.close()
        atexit.register(cleanUp)

    def run(self):
        uvicorn.run(self.server, host="127.0.0.1", port=8090)

apiServer = ApiServer()
def getApiServer()->ApiServer:
    return apiServer

@apiServer.server.post("/chat/invoke")
def read_item(req: ChatRequest, server: ApiServer= Depends(getApiServer)):
    resp = server.yourAgent.webRun(req.thread_id, "message", req.message)
    # return {"session_id": req.sessionId, "role":resp["role"], "opType":resp["opType"], "content":resp["content"] }
    content = resp["content"]
    interruptId = "1"
    if resp["opType"] == "interrupt" :
        interruptContent = resp["content"]
        return {"interrupt": {"value": interruptContent, "interrupt_id": interruptId}}
    return {"content": content}

@apiServer.server.post("/chat/resume")
def read_item(req: ResumeRequest, server: ApiServer= Depends(getApiServer)):
    resp = server.yourAgent.webRun(req.thread_id, "interrupt", req.resume)
    content = resp["content"]
    interruptId = "1"
    if resp["opType"] == "interrupt":
        interruptContent = resp["content"]
        return {"interrupt": {"value": interruptContent, "interrupt_id": interruptId}}
    return {"content": content}

@apiServer.server.post("/chat/history")
def read_item(req: AgentInvokeRequest, server: ApiServer= Depends(getApiServer)):
    resp = server.yourAgent.webHistory(req.sessionId)
    return {"session_id": req.sessionId, "role":"system", "opType":"history", "content":resp }