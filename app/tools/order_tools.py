from typing import Union
from langchain_core.tools import tool
from app.database.database import SessionLocal
from app.database.models import Order, Customer

@tool
def get_order_status(order_id: Union[int, str]) -> dict:
    """Retrieve current status, items, address, and details for an order using its Order ID (e.g., 1001, 1002, 1003)."""
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
                "message": f"Order #{order_id_int} was not found in our system. Please check your order number."
            }

        return {
            "success": True,
            "order_id": order.id,
            "customer_id": order.customer_id,
            "product_name": order.product_name,
            "status": order.status,
            "price": order.price,
            "shipping_address": order.shipping_address or "Standard Shipping Address",
            "order_date": order.order_date.strftime("%Y-%m-%d %H:%M UTC") if order.order_date else "Unknown",
            "message": f"Order #{order.id} for {order.product_name} is currently '{order.status}'."
        }
    except Exception as e:
        return {
            "success": False,
            "error": "DATABASE_ERROR",
            "message": f"Database error querying order #{order_id_int}: {str(e)}"
        }
    finally:
        db.close()


@tool
def get_customer_orders(customer_id: Union[int, str]) -> dict:
    """Retrieve all order history for a specific customer ID (e.g., 1 or 2)."""
    try:
        customer_id_int = int(customer_id)
    except (ValueError, TypeError):
        return {
            "success": False,
            "error": "INVALID_CUSTOMER_ID",
            "message": f"Invalid customer ID '{customer_id}'. Customer ID must be an integer."
        }

    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id_int).first()
        if not customer:
            return {
                "success": False,
                "error": "CUSTOMER_NOT_FOUND",
                "message": f"Customer with ID {customer_id_int} was not found."
            }

        orders = db.query(Order).filter(Order.customer_id == customer_id_int).all()
        order_list = [
            {
                "order_id": o.id,
                "product_name": o.product_name,
                "status": o.status,
                "price": o.price,
                "shipping_address": o.shipping_address,
                "order_date": o.order_date.strftime("%Y-%m-%d") if o.order_date else "Unknown"
            }
            for o in orders
        ]

        return {
            "success": True,
            "customer_id": customer.id,
            "customer_name": customer.name,
            "total_orders": len(order_list),
            "orders": order_list,
            "message": f"Found {len(order_list)} orders for customer {customer.name}."
        }
    except Exception as e:
        return {
            "success": False,
            "error": "DATABASE_ERROR",
            "message": f"Database error querying customer orders: {str(e)}"
        }
    finally:
        db.close()


@tool
def cancel_order(order_id: Union[int, str]) -> dict:
    """Cancel an active order if its status is still 'Processing'. Shipped or Delivered orders cannot be cancelled."""
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
                "message": f"Cannot cancel Order #{order_id_int}: order was not found in our database."
            }

        if order.status.lower() == "cancelled":
            return {
                "success": False,
                "error": "ALREADY_CANCELLED",
                "message": f"Order #{order_id_int} is already cancelled."
            }

        if order.status.lower() in ["shipped", "delivered"]:
            return {
                "success": False,
                "error": "CANNOT_CANCEL_SHIPPED_ORDER",
                "current_status": order.status,
                "message": (
                    f"Order #{order_id_int} cannot be cancelled because it is already '{order.status}'. "
                    "Once an item has shipped, it cannot be intercepted. You may initiate a return "
                    "after receiving the product according to our 30-day return policy."
                )
            }

        if order.status.lower() == "processing":
            order.status = "Cancelled"
            db.commit()
            return {
                "success": True,
                "order_id": order.id,
                "product_name": order.product_name,
                "status": "Cancelled",
                "message": f"Order #{order.id} for '{order.product_name}' has been successfully cancelled and a full refund of ${order.price:.2f} has been credited."
            }

        return {
            "success": False,
            "error": "UNKNOWN_ORDER_STATUS",
            "message": f"Order #{order_id_int} has unhandled status '{order.status}'."
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": "DATABASE_ERROR",
            "message": f"Database error cancelling order #{order_id_int}: {str(e)}"
        }
    finally:
        db.close()


@tool
def update_shipping_address(order_id: Union[int, str], new_address: str) -> dict:
    """Update the destination shipping address for an order while it is still in 'Processing' status."""
    if not new_address or not str(new_address).strip():
        return {
            "success": False,
            "error": "EMPTY_ADDRESS",
            "message": "New shipping address cannot be empty."
        }

    try:
        order_id_int = int(order_id)
    except (ValueError, TypeError):
        return {
            "success": False,
            "error": "INVALID_ORDER_ID",
            "message": f"Invalid order ID '{order_id}'."
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

        if order.status.lower() != "processing":
            return {
                "success": False,
                "error": "CANNOT_UPDATE_ADDRESS",
                "current_status": order.status,
                "message": f"Cannot update shipping address for Order #{order_id_int} because it is already '{order.status}'."
            }

        order.shipping_address = str(new_address).strip()
        db.commit()
        return {
            "success": True,
            "order_id": order.id,
            "shipping_address": order.shipping_address,
            "message": f"Shipping address for Order #{order.id} has been updated to: {order.shipping_address}"
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": "DATABASE_ERROR",
            "message": f"Database error updating shipping address: {str(e)}"
        }
    finally:
        db.close()
