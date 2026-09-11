from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    State definition for the Customer Support LangGraph workflow.
    
    Attributes:
        messages: Chronological conversation history
        intent: Detected user intent category
        customer_id: Optional customer context identifier
        session_id: Active session / thread identifier
        escalated: True if conversation escalated to human
        traces: Execution and reasoning step log for the dashboard
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    intent: Optional[str]
    customer_id: Optional[int]
    session_id: Optional[str]
    escalated: Optional[bool]
    traces: Optional[List[Dict[str, Any]]]
