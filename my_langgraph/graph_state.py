from langgraph.graph import MessagesState

class YourAgentState(MessagesState):
    intputStr: str
    outPutStr: str