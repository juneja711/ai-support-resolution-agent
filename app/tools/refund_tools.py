from datetime import datetime, timezone
from typing import Union
from langchain_core.tools import tool
from app.database.database import SessionLocal
from app.database.models import Order, SupportTicket

@tool
def check_refund_eligibility(order_id: Union[int, str]) -> dict:
    """Check if an order is eligible for a refund according to company policy (must be Delivered and within 30 days)."""
    try:
        order_id_int = int(order_id)
    except (ValueError, TypeError):
        return {
            "success": False,
            "error": "INVALID_ORDER_ID",
            "message": f"Invalid order ID '{order_id}'. Order ID must be an integer."
        }

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id_int).first()
        if not order:
            return {
                "success": False,
                "error": "ORDER_NOT_FOUND",
                "message": f"Order #{order_id_int} was not found."
            }

        # Check status
        status_lower = order.status.lower()
        if status_lower == "cancelled":
            return {
                "success": True,
                "eligible": False,
                "reason": "ALREADY_CANCELLED",
                "order_id": order.id,
                "status": order.status,
                "message": f"Order #{order_id_int} is already cancelled. Refund was issued at the time of cancellation."
            }

        if status_lower == "processing":
            return {
                "success": True,
                "eligible": False,
                "reason": "ORDER_PROCESSING",
                "order_id": order.id,
                "status": order.status,
                "message": f"Order #{order_id_int} is currently Processing. You can cancel this order directly for an immediate full refund."
            }

        if status_lower == "shipped":
            return {
                "success": True,
                "eligible": False,
                "reason": "ORDER_IN_TRANSIT",
                "order_id": order.id,
                "status": order.status,
                "message": f"Order #{order_id_int} is currently Shipped and in transit. Please wait for delivery to inspect the item before requesting a refund."
            }

        if status_lower == "delivered":
            # Calculate days since order/delivery
            now = datetime.now(timezone.utc)
            order_date = order.order_date
            if order_date.tzinfo is None:
                order_date = order_date.replace(tzinfo=timezone.utc)
            
            days_since = (now - order_date).days
            if days_since <= 30:
                return {
                    "success": True,
                    "eligible": True,
                    "order_id": order.id,
                    "product_name": order.product_name,
                    "price": order.price,
                    "days_since_delivery": days_since,
                    "message": f"Order #{order_id_int} for {order.product_name} is eligible for a refund (delivered {days_since} days ago, within the 30-day window)."
                }
            else:
                return {
                    "success": True,
                    "eligible": False,
                    "reason": "WINDOW_EXPIRED",
                    "order_id": order.id,
                    "days_since_delivery": days_since,
                    "message": f"Order #{order_id_int} is not eligible for a refund because it was delivered {days_since} days ago (exceeds our 30-day refund window)."
                }

        return {
            "success": False,
            "error": "UNKNOWN_STATUS",
            "message": f"Order #{order_id_int} has unhandled status '{order.status}'."
        }
    except Exception as e:
        return {
            "success": False,
            "error": "DATABASE_ERROR",
            "message": f"Database error checking refund eligibility for order #{order_id_int}: {str(e)}"
        }
    finally:
        db.close()


@tool
def create_refund_request(order_id: Union[int, str]) -> dict:
    """Submit a formal refund request for an eligible order."""
    try:
        order_id_int = int(order_id)
    except (ValueError, TypeError):
        return {
            "success": False,
            "error": "INVALID_ORDER_ID",
            "message": f"Invalid order ID '{order_id}'. Order ID must be an integer."
        }

    # First verify eligibility
    eligibility = check_refund_eligibility.func(order_id_int)
    if not eligibility.get("success"):
        return eligibility

    if not eligibility.get("eligible"):
        return {
            "success": False,
            "error": "NOT_ELIGIBLE",
            "reason": eligibility.get("reason"),
            "message": f"Cannot submit refund request: {eligibility.get('message')}"
        }

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id_int).first()
        ticket = SupportTicket(
            customer_id=order.customer_id,
            issue=f"Refund Request for Order #{order.id} ({order.product_name}) - Amount: ${order.price:.2f}",
            status="Open",
            created_at=datetime.now(timezone.utc)
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        return {
            "success": True,
            "order_id": order.id,
            "ticket_id": ticket.id,
            "refund_amount": order.price,
            "status": "Submitted",
            "message": (
                f"Refund request for Order #{order.id} ({order.product_name}) has been approved and registered "
                f"under Support Ticket #{ticket.id}. A full refund of ${order.price:.2f} will be credited to "
                "your original payment method within 5-7 business days."
            )
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": "DATABASE_ERROR",
            "message": f"Database error creating refund request: {str(e)}"
        }
    finally:
        db.close()
