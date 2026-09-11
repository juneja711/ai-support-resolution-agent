import re
from datetime import datetime, timezone
from typing import Literal, Dict, Any, List
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.agents.state import AgentState
from app.tools.order_tools import get_order_status, get_customer_orders, cancel_order, update_shipping_address
from app.tools.refund_tools import check_refund_eligibility, create_refund_request
from app.tools.support_tools import create_support_ticket, escalate_to_human_agent
from app.rag.retriever import lookup_company_policy, query_knowledge_base

# Tools list
TOOLS = [
    get_order_status,
    get_customer_orders,
    cancel_order,
    update_shipping_address,
    check_refund_eligibility,
    create_refund_request,
    create_support_ticket,
    escalate_to_human_agent,
    lookup_company_policy
]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

SYSTEM_PROMPT = """You are NovaTech's official AI Customer Support & Resolution Agent.
Your primary objective is to autonomously diagnose customer problems, execute appropriate database actions or knowledge base lookups, and resolve customer issues clearly and empathetically.

AUTONOMOUS MULTI-STEP REASONING RULES:
1. Intent & Context Understanding:
   - Identify what the customer actually wants even if phrased casually or containing multiple complaints.
   - Use conversation memory: if the user refers to "it", "my order", or previous details, correlate with earlier messages.
2. Step-by-Step Resolution:
   - For queries like "My order 1003 hasn't arrived and I want a refund":
     a. First check the order status using `get_order_status(order_id=1003)`.
     b. If the order is still "Processing" (not yet shipped), explain that it has not dispatched or arrived yet.
     c. Explain that while a delivered return refund isn't applicable yet, they can cancel the order right now for an immediate 100% full refund, or offer to cancel it for them.
   - For order cancellations: Check order status. If "Processing", invoke `cancel_order`. If "Shipped", reject cancellation with reference to the 30-day return policy upon delivery.
   - For address updates: Use `update_shipping_address`. Only allowed if status is "Processing".
3. Human Escalation:
   - If the customer explicitly requests a human ("I want a human", "talk to a representative", "connect me to a person", "I've tried everything"):
     Immediately invoke `escalate_to_human_agent` with the customer ID and conversation summary.
4. Grounding:
   - NEVER invent order statuses, tracking numbers, or company policies.
   - NEVER promise actions without calling the corresponding tool.
"""

# In-memory store for global trace logs displayed on the Agent Dashboard
GLOBAL_ACTIVITY_LOGS: List[Dict[str, Any]] = []

def record_activity_log(session_id: str, action: str, details: Any):
    """Record an event to the in-memory dashboard audit trace."""
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "session_id": session_id or "default",
        "action": action,
        "details": details
    }
    GLOBAL_ACTIVITY_LOGS.insert(0, entry)
    # Cap at last 100 traces
    if len(GLOBAL_ACTIVITY_LOGS) > 100:
        GLOBAL_ACTIVITY_LOGS.pop()


def detect_intent(text: str) -> str:
    """Classify user query into support intent categories."""
    t = text.lower()
    if any(k in t for k in ["human", "representative", "agent", "person", "operator", "speak to someone", "tried everything"]):
        return "HUMAN_ESCALATION"
    if any(k in t for k in ["address", "change shipping", "update address"]):
        return "UPDATE_ADDRESS"
    if any(k in t for k in ["cancel order", "cancellation", "cancel my", "cancel it"]):
        return "ORDER_CANCELLATION"
    if any(k in t for k in ["refund", "return my", "money back", "reimbursement", "hasn't arrived and"]):
        return "REFUND_OR_STATUS"
    if any(k in t for k in ["where is my order", "order status", "track order", "track my order", "order #", "order id", "status of order"]) or re.search(r"order\s*#?\s*\d+", t):
        return "ORDER_STATUS"
    if any(k in t for k in ["policy", "shipping time", "how long does shipping", "how to return", "delivery time"]):
        return "POLICY_INQUIRY"
    return "GENERAL_INQUIRY"


def get_llm():
    """Return configured ChatOpenAI instance if API key is present."""
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.startswith("sk-"):
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0
        )
    return None


# Multi-turn context tracker for offline / demo mode
_OFFLINE_SESSION_MEMORY: Dict[str, Dict[str, Any]] = {}

def agent_node(state: AgentState) -> dict:
    """Core Agent Node: Observes state, decides actions/tools, or synthesizes answer."""
    messages = list(state.get("messages", []))
    session_id = state.get("session_id") or "default"
    traces = list(state.get("traces") or [])

    # Find the most recent user message
    last_user_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    intent = state.get("intent") or detect_intent(last_user_msg)

    llm = get_llm()
    if llm:
        try:
            llm_with_tools = llm.bind_tools(TOOLS)
            prompt_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
            ai_msg = llm_with_tools.invoke(prompt_messages)
            
            trace_entry = {
                "step": "AGENT_REASONING",
                "tool_calls": [tc["name"] for tc in getattr(ai_msg, "tool_calls", [])] if getattr(ai_msg, "tool_calls", None) else [],
                "content_preview": ai_msg.content[:100] if ai_msg.content else "Invoking tools..."
            }
            traces.append(trace_entry)
            record_activity_log(session_id, "LLM_DECISION", trace_entry)

            return {
                "messages": [ai_msg],
                "intent": intent,
                "traces": traces
            }
        except Exception as e:
            print(f"⚠️ OpenAI call failed: {e}. Falling back to deterministic reasoning loop.")

    # Offline / Demo Multi-Turn Autonomous Reasoning
    ai_msg, new_intent, step_trace = _deterministic_multistep_reasoning(messages, session_id, intent)
    traces.append(step_trace)
    record_activity_log(session_id, "AGENT_DECISION", step_trace)

    return {
        "messages": [ai_msg],
        "intent": new_intent,
        "traces": traces
    }


def _deterministic_multistep_reasoning(messages: List[BaseMessage], session_id: str, current_intent: str) -> tuple[AIMessage, str, dict]:
    """Autonomous reasoning engine for offline/demo operation with multi-turn memory."""
    if session_id not in _OFFLINE_SESSION_MEMORY:
        _OFFLINE_SESSION_MEMORY[session_id] = {
            "last_order_id": None,
            "escalated": False
        }
    mem = _OFFLINE_SESSION_MEMORY[session_id]

    last_msg = messages[-1]
    last_user_text = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")

    # Check for order ID in message or recall from memory
    order_id_match = re.search(r"\b(100[1-9]|\d{4,6})\b", last_user_text)
    if order_id_match:
        mem["last_order_id"] = int(order_id_match.group(1))
    
    order_id = mem.get("last_order_id")

    # If the previous step was a tool execution, synthesize the result
    if isinstance(last_msg, ToolMessage):
        content = last_msg.content
        tool_name = last_msg.name

        if tool_name == "get_order_status":
            import ast
            try:
                data = ast.literal_eval(content)
                status = data.get("status")
                pname = data.get("product_name")
                oid = data.get("order_id")
                
                # Compound condition: user said hasn't arrived & wants refund
                if "hasn't arrived" in last_user_text.lower() or "not arrived" in last_user_text.lower():
                    if status == "Processing":
                        resp = (
                            f"I checked Order #{oid} for {pname}. Its current status is 'Processing' and it has not shipped yet. "
                            f"Because it has not been delivered, a standard return refund is not applicable, but you can cancel the order right now "
                            f"for an immediate 100% full refund of ${data.get('price'):.2f}. Would you like me to cancel it for you?"
                        )
                        return AIMessage(content=resp), "ORDER_STATUS_REFUND_COMPOUND", {"step": "SYNTHESIZE_COMPOUND", "output": resp}
                
                resp = f"Order #{oid} for {pname} is currently '{status}'. Shipping destination: {data.get('shipping_address')}."
                return AIMessage(content=resp), "ORDER_STATUS", {"step": "SYNTHESIZE_STATUS", "output": resp}
            except Exception:
                pass

        if tool_name == "escalate_to_human_agent":
            mem["escalated"] = True
            import ast
            try:
                data = ast.literal_eval(content)
                resp = data.get("message", content)
            except Exception:
                resp = content
            return AIMessage(content=resp), "HUMAN_ESCALATION", {"step": "ESCALATION_COMPLETE", "output": resp}

        # Generic tool synthesis
        import ast
        try:
            data = ast.literal_eval(content)
            resp = data.get("message", content)
        except Exception:
            resp = content
        return AIMessage(content=resp), current_intent, {"step": "TOOL_SYNTHESIS", "output": resp}

    # Human Escalation Request
    if any(k in last_user_text.lower() for k in ["human", "representative", "person", "operator", "speak to someone", "tried everything", "escalate"]):
        mem["escalated"] = True
        return AIMessage(
            content="",
            tool_calls=[{
                "name": "escalate_to_human_agent",
                "args": {
                    "reason": last_user_text,
                    "conversation_summary": f"User expressed frustration or requested human handoff: '{last_user_text}'",
                    "customer_id": 1,
                    "urgency": "High"
                },
                "id": "call_escalate_1"
            }]
        ), "HUMAN_ESCALATION", {"step": "DISPATCH_TOOL", "tool": "escalate_to_human_agent"}

    # Cancellation with pronoun "it" or direct mention
    if any(k in last_user_text.lower() for k in ["cancel it", "cancel order", "cancel my", "cancellation"]):
        if order_id:
            return AIMessage(
                content="",
                tool_calls=[{"name": "cancel_order", "args": {"order_id": order_id}, "id": "call_cancel_1"}]
            ), "ORDER_CANCELLATION", {"step": "DISPATCH_TOOL", "tool": "cancel_order", "order_id": order_id}
        else:
            return AIMessage(content="Which Order ID would you like to cancel? (e.g., Order 1003)"), "ORDER_CANCELLATION", {"step": "PROMPT_PARAM"}

    # Update Shipping Address
    if any(k in last_user_text.lower() for k in ["change address", "update address", "shipping address"]):
        addr_match = re.search(r"(?:to|address:?)\s+(.+)$", last_user_text, re.IGNORECASE)
        new_addr = addr_match.group(1) if addr_match else "456 Market St, San Francisco, CA"
        if order_id:
            return AIMessage(
                content="",
                tool_calls=[{"name": "update_shipping_address", "args": {"order_id": order_id, "new_address": new_addr}, "id": "call_addr_1"}]
            ), "UPDATE_ADDRESS", {"step": "DISPATCH_TOOL", "tool": "update_shipping_address"}
        else:
            return AIMessage(content="Please provide the Order ID and your new address."), "UPDATE_ADDRESS", {"step": "PROMPT_PARAM"}

    # Order status or compound query (hasn't arrived / status)
    if order_id and ("where is" in last_user_text.lower() or "status" in last_user_text.lower() or "hasn't arrived" in last_user_text.lower() or "not arrived" in last_user_text.lower()):
        return AIMessage(
            content="",
            tool_calls=[{"name": "get_order_status", "args": {"order_id": order_id}, "id": "call_status_1"}]
        ), "ORDER_STATUS", {"step": "DISPATCH_TOOL", "tool": "get_order_status", "order_id": order_id}

    # Refund inquiry
    if "refund" in last_user_text.lower() or "return" in last_user_text.lower():
        if order_id:
            return AIMessage(
                content="",
                tool_calls=[{"name": "check_refund_eligibility", "args": {"order_id": order_id}, "id": "call_refund_1"}]
            ), "REFUND_REQUEST", {"step": "DISPATCH_TOOL", "tool": "check_refund_eligibility", "order_id": order_id}
        else:
            return AIMessage(
                content="",
                tool_calls=[{"name": "lookup_company_policy", "args": {"query": "refund return policy requirements"}, "id": "call_policy_1"}]
            ), "POLICY_INQUIRY", {"step": "DISPATCH_TOOL", "tool": "lookup_company_policy"}

    # Policy inquiry
    if any(k in last_user_text.lower() for k in ["policy", "shipping", "delivery", "days"]):
        return AIMessage(
            content="",
            tool_calls=[{"name": "lookup_company_policy", "args": {"query": last_user_text}, "id": "call_policy_2"}]
        ), "POLICY_INQUIRY", {"step": "DISPATCH_TOOL", "tool": "lookup_company_policy"}

    # General Greeting
    return AIMessage(
        content="Hello! I am your AI Customer Support Assistant. How can I help you with your order, refund, cancellation, or store policy today?"
    ), "GENERAL_INQUIRY", {"step": "GENERAL_RESPONSE"}


def should_continue(state: AgentState) -> Literal["tools_node", "end"]:
    """Conditional edge: check if latest message has tool calls."""
    messages = state.get("messages", [])
    if not messages:
        return "end"
    last_msg = messages[-1]
    if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", None):
        return "tools_node"
    return "end"


def tools_node(state: AgentState) -> dict:
    """Execute all tool calls and return ToolMessages back to the agent loop."""
    messages = state.get("messages", [])
    last_message = messages[-1]
    tool_messages = []
    session_id = state.get("session_id") or "default"
    traces = list(state.get("traces") or [])

    for tool_call in getattr(last_message, "tool_calls", []):
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id", "call_1")

        if tool_name in TOOLS_BY_NAME:
            try:
                result = TOOLS_BY_NAME[tool_name].invoke(tool_args)
                tool_messages.append(
                    ToolMessage(
                        content=str(result),
                        name=tool_name,
                        tool_call_id=tool_id
                    )
                )
                trace_item = {"step": "TOOL_RESULT", "tool": tool_name, "result": str(result)[:120]}
                traces.append(trace_item)
                record_activity_log(session_id, f"TOOL:{tool_name}", result)
            except Exception as e:
                tool_messages.append(
                    ToolMessage(
                        content=f"Error executing {tool_name}: {str(e)}",
                        name=tool_name,
                        tool_call_id=tool_id
                    )
                )
        else:
            tool_messages.append(
                ToolMessage(
                    content=f"Tool {tool_name} not found.",
                    name=tool_name,
                    tool_call_id=tool_id
                )
            )

    return {"messages": tool_messages, "traces": traces}


def build_support_graph():
    """Construct and compile the cyclic LangGraph ReAct agent with MemorySaver."""
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools_node", tools_node)

    # Add Edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools_node": "tools_node",
            "end": END
        }
    )
    # Loop back from tools to agent for multi-step reasoning
    workflow.add_edge("tools_node", "agent")

    # In-memory checkpointer for multi-turn conversational threads
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

# Global compiled agent instance
support_agent = build_support_graph()
