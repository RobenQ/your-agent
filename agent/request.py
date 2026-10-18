from typing import Optional

from pydantic import BaseModel


class AgentInvokeRequest(BaseModel):
    sessionId: str
    opType: str
    content: str

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


class ResumeRequest(BaseModel):
    thread_id: str
    resume: str
    interrupt_id: Optional[str] = None