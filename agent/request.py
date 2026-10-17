from pydantic import BaseModel


class AgentInvokeRequest(BaseModel):
    sessionId: str
    opType: str
    content: str