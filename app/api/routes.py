import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from app.agents.graph import support_agent, GLOBAL_ACTIVITY_LOGS, record_activity_log
from app.tools.order_tools import get_order_status, cancel_order, update_shipping_address
from app.tools.refund_tools import check_refund_eligibility
from app.tools.support_tools import create_support_ticket, escalate_to_human_agent
from app.database.database import SessionLocal, reset_db
from app.database.models import Customer, Order, SupportTicket

router = APIRouter()

# ----------------- Pydantic Schemas -----------------

class ChatRequest(BaseModel):
    message: str = Field(..., description="Customer message or inquiry")
    session_id: Optional[str] = Field(default=None, description="Conversation session ID for memory")
    customer_id: Optional[int] = Field(default=1, description="Optional customer ID")

class ChatResponse(BaseModel):
    response: str
    intent: str
    session_id: str
    escalated: bool = False
    traces: List[Dict[str, Any]] = []
    success: bool = True

class SupportTicketRequest(BaseModel):
    issue: str = Field(..., description="Description of the customer issue")
    customer_id: Optional[int] = Field(default=1, description="Customer ID")
    priority: Optional[str] = Field(default="Normal", description="Priority level: Normal or Urgent")

class AddressUpdateRequest(BaseModel):
    new_address: str = Field(..., description="New destination address")


# ----------------- Core Chat & Support Endpoints -----------------

@router.get("/health", tags=["System"])
def health_check():
    """Health check endpoint to verify service and database connectivity."""
    db_status = "connected"
    try:
        db = SessionLocal()
        db.query(Customer).count()
        db.close()
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "app": "AI Customer Support & Resolution Agent",
        "database": db_status
    }


@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat_endpoint(payload: ChatRequest):
    """
    Primary customer support chat endpoint with multi-turn memory and agent reasoning traces.
    """
    clean_message = payload.message.strip() if payload.message else ""
    if not clean_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User message cannot be empty."
        )

    session_id = payload.session_id or str(uuid.uuid4())[:8]

    try:
        record_activity_log(session_id, "USER_MESSAGE", clean_message)

        initial_state = {
            "messages": [HumanMessage(content=clean_message)],
            "customer_id": payload.customer_id,
            "session_id": session_id,
            "traces": []
        }
        
        # Invoke cyclic graph with thread checkpointer
        config = {"configurable": {"thread_id": session_id}}
        result = support_agent.invoke(initial_state, config=config)
        
        messages = result.get("messages", [])
        final_response = messages[-1].content if messages else "I am sorry, I could not process your inquiry."
        intent = result.get("intent") or "GENERAL_INQUIRY"
        traces = result.get("traces") or []
        escalated = result.get("escalated") or ("escalated" in final_response.lower() or intent == "HUMAN_ESCALATION")

        record_activity_log(session_id, "AGENT_RESPONSE", {
            "response": final_response[:100],
            "intent": intent,
            "escalated": escalated
        })

        return ChatResponse(
            response=final_response,
            intent=intent,
            session_id=session_id,
            escalated=escalated,
            traces=traces,
            success=True
        )
    except Exception as e:
        return ChatResponse(
            response=f"An error occurred while processing your request: {str(e)}",
            intent="ERROR",
            session_id=session_id,
            escalated=False,
            traces=[],
            success=False
        )


@router.get("/orders/{order_id}", tags=["Orders"])
def get_order_endpoint(order_id: int):
    """Retrieve details and status for an order by ID."""
    result = get_order_status.invoke({"order_id": order_id})
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result


@router.post("/orders/{order_id}/cancel", tags=["Orders"])
def cancel_order_endpoint(order_id: int):
    """Cancel an active order if it is in 'Processing' status."""
    result = cancel_order.invoke({"order_id": order_id})
    if not result.get("success"):
        if result.get("error") == "ORDER_NOT_FOUND":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))
    return result


@router.get("/orders/{order_id}/refund", tags=["Orders"])
def check_refund_endpoint(order_id: int):
    """Check whether an order is eligible for a refund according to company policy."""
    result = check_refund_eligibility.invoke({"order_id": order_id})
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result


@router.put("/orders/{order_id}/address", tags=["Orders"])
def update_address_endpoint(order_id: int, payload: AddressUpdateRequest):
    """Update shipping address for a processing order."""
    result = update_shipping_address.invoke({"order_id": order_id, "new_address": payload.new_address})
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))
    return result


@router.post("/support/ticket", tags=["Support"])
def create_ticket_endpoint(payload: SupportTicketRequest):
    """Create a new human customer support ticket."""
    if not payload.issue or not payload.issue.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Issue description cannot be empty.")

    result = create_support_ticket.invoke({
        "customer_id": payload.customer_id,
        "issue": payload.issue,
        "priority": payload.priority or "Normal"
    })
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("message"))
    return result


# ----------------- Agent Dashboard API Endpoints -----------------

@router.get("/api/dashboard/overview", tags=["Dashboard"])
def dashboard_overview():
    """Retrieve statistical summary for the Agent Dashboard."""
    db = SessionLocal()
    try:
        total_orders = db.query(Order).count()
        orders = db.query(Order).all()
        order_status_counts = {}
        for o in orders:
            order_status_counts[o.status] = order_status_counts.get(o.status, 0) + 1

        total_tickets = db.query(SupportTicket).count()
        tickets = db.query(SupportTicket).all()
        ticket_status_counts = {}
        escalated_count = 0
        for t in tickets:
            ticket_status_counts[t.status] = ticket_status_counts.get(t.status, 0) + 1
            if t.status == "Escalated" or t.priority in ["Urgent", "Escalated"]:
                escalated_count += 1

        total_customers = db.query(Customer).count()

        return {
            "total_orders": total_orders,
            "order_status_counts": order_status_counts,
            "total_tickets": total_tickets,
            "ticket_status_counts": ticket_status_counts,
            "escalated_count": escalated_count,
            "total_customers": total_customers
        }
    finally:
        db.close()


@router.get("/api/dashboard/orders", tags=["Dashboard"])
def dashboard_orders():
    """List all orders in the SQLite database."""
    db = SessionLocal()
    try:
        orders = db.query(Order).order_by(Order.id.asc()).all()
        return [
            {
                "id": o.id,
                "customer_id": o.customer_id,
                "customer_name": o.customer.name if o.customer else "Unknown",
                "product_name": o.product_name,
                "price": o.price,
                "status": o.status,
                "shipping_address": o.shipping_address,
                "order_date": o.order_date.strftime("%Y-%m-%d") if o.order_date else "Unknown"
            }
            for o in orders
        ]
    finally:
        db.close()


@router.get("/api/dashboard/tickets", tags=["Dashboard"])
def dashboard_tickets():
    """List all support tickets including human escalations."""
    db = SessionLocal()
    try:
        tickets = db.query(SupportTicket).order_by(SupportTicket.id.desc()).all()
        return [
            {
                "id": t.id,
                "customer_id": t.customer_id,
                "customer_name": t.customer.name if t.customer else "Unknown",
                "issue": t.issue,
                "status": t.status,
                "priority": t.priority,
                "assigned_agent": t.assigned_agent,
                "notes": t.notes,
                "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "Unknown"
            }
            for t in tickets
        ]
    finally:
        db.close()


@router.get("/api/dashboard/traces", tags=["Dashboard"])
def dashboard_traces():
    """Retrieve recent agent decision-making and execution traces."""
    return GLOBAL_ACTIVITY_LOGS[:40]


@router.post("/api/dashboard/reset", tags=["Dashboard"])
def dashboard_reset():
    """Reset the database to clean demo state."""
    reset_db()
    record_activity_log("system", "DATABASE_RESET", "Demo orders and tickets restored to initial seed state.")
    return {"success": True, "message": "Database successfully reset to initial demo state."}
