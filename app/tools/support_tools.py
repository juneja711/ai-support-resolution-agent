from datetime import datetime, timezone
from typing import Union, Optional
from langchain_core.tools import tool
from app.database.database import SessionLocal
from app.database.models import SupportTicket, Customer

@tool
def create_support_ticket(
    customer_id: Optional[Union[int, str]],
    issue: str,
    priority: str = "Normal"
) -> dict:
    """Create a standard customer support ticket for tracking customer inquiries."""
    if not issue or not str(issue).strip():
        return {
            "success": False,
            "error": "EMPTY_ISSUE",
            "message": "Cannot create support ticket: issue description cannot be empty."
        }

    try:
        customer_id_int = int(customer_id) if customer_id else 1
    except (ValueError, TypeError):
        customer_id_int = 1

    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id_int).first()
        if not customer:
            customer = db.query(Customer).first()
            if customer:
                customer_id_int = customer.id

        ticket = SupportTicket(
            customer_id=customer_id_int,
            issue=str(issue).strip(),
            status="Open",
            priority=priority,
            assigned_agent="Tier-1 Support Team",
            created_at=datetime.now(timezone.utc)
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        return {
            "success": True,
            "ticket_id": ticket.id,
            "customer_id": ticket.customer_id,
            "issue": ticket.issue,
            "status": ticket.status,
            "priority": ticket.priority,
            "message": (
                f"Support Ticket #{ticket.id} has been created successfully. "
                "Our team will review your inquiry shortly."
            )
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": "DATABASE_ERROR",
            "message": f"Database error creating support ticket: {str(e)}"
        }
    finally:
        db.close()


@tool
def escalate_to_human_agent(
    reason: str,
    conversation_summary: Optional[str] = None,
    customer_id: Optional[Union[int, str]] = 1,
    urgency: str = "High"
) -> dict:
    """Escalate the customer conversation directly to a Senior Human Support Specialist when the customer requests a human or issue cannot be resolved by AI."""
    try:
        customer_id_int = int(customer_id) if customer_id else 1
    except (ValueError, TypeError):
        customer_id_int = 1

    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id_int).first()
        if not customer:
            customer = db.query(Customer).first()
            if customer:
                customer_id_int = customer.id

        summary = conversation_summary or reason or "Customer requested direct human agent escalation."
        ticket = SupportTicket(
            customer_id=customer_id_int,
            issue=f"[HUMAN ESCALATION] {reason}",
            status="Escalated",
            priority="Urgent" if urgency.lower() in ["high", "urgent"] else "High",
            assigned_agent="Senior Human Specialist (Tier-2 Escalations)",
            notes=f"Escalation Reason: {reason}\nContext Summary: {summary}",
            created_at=datetime.now(timezone.utc)
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        return {
            "success": True,
            "escalated": True,
            "ticket_id": ticket.id,
            "status": "Escalated",
            "priority": ticket.priority,
            "assigned_agent": ticket.assigned_agent,
            "estimated_wait_time": "3-5 minutes",
            "message": (
                f"I have escalated your request to our Senior Human Support Team. "
                f"Your Priority Ticket ID is #{ticket.id} (Priority: {ticket.priority}). "
                "A human representative has been notified and will take over this conversation shortly."
            )
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": "DATABASE_ERROR",
            "message": f"Database error escalating to human agent: {str(e)}"
        }
    finally:
        db.close()
