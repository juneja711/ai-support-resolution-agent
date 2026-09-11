import pytest
from fastapi.testclient import TestClient

from app.database.database import reset_db, SessionLocal
from app.database.models import Order, Customer, SupportTicket
from app.tools.order_tools import get_order_status, cancel_order, get_customer_orders, update_shipping_address
from app.tools.refund_tools import check_refund_eligibility, create_refund_request
from app.tools.support_tools import create_support_ticket, escalate_to_human_agent
from app.rag.retriever import query_knowledge_base
from app.main import app

@pytest.fixture(autouse=True)
def clean_db():
    """Reset the database to known clean state before each test."""
    reset_db()

# 1. Order Status Tool Tests
def test_get_order_status_success():
    """Test retrieving an existing order (Order 1001)."""
    result = get_order_status.invoke({"order_id": 1001})
    assert result["success"] is True
    assert result["order_id"] == 1001
    assert result["product_name"] == "Laptop"
    assert result["status"] == "Shipped"

def test_get_order_status_invalid_order():
    """Test querying a non-existent order ID."""
    result = get_order_status.invoke({"order_id": 99999})
    assert result["success"] is False
    assert result["error"] == "ORDER_NOT_FOUND"

def test_get_order_status_non_integer():
    """Test querying with an invalid non-integer string."""
    result = get_order_status.invoke({"order_id": "invalid_abc"})
    assert result["success"] is False
    assert result["error"] == "INVALID_ORDER_ID"

# 2. Customer Orders Tool Tests
def test_get_customer_orders_success():
    """Test retrieving order history for Customer 1."""
    result = get_customer_orders.invoke({"customer_id": 1})
    assert result["success"] is True
    assert result["customer_id"] == 1
    assert result["total_orders"] >= 2

# 3. Order Cancellation Tool Tests
def test_cancel_order_shipped_rejection():
    """Test that an order that has already shipped cannot be cancelled."""
    result = cancel_order.invoke({"order_id": 1001})
    assert result["success"] is False
    assert result["error"] == "CANNOT_CANCEL_SHIPPED_ORDER"
    assert "already 'Shipped'" in result["message"]

def test_cancel_order_processing_success():
    """Test cancelling an order that is currently Processing (Order 1003)."""
    result = cancel_order.invoke({"order_id": 1003})
    assert result["success"] is True
    assert result["status"] == "Cancelled"

    db = SessionLocal()
    order = db.query(Order).filter(Order.id == 1003).first()
    assert order.status == "Cancelled"
    db.close()

# 4. Shipping Address Update Tool Tests
def test_update_shipping_address_processing_order():
    """Test updating destination address on processing order 1003."""
    result = update_shipping_address.invoke({
        "order_id": 1003,
        "new_address": "555 Market St, Suite 100, San Francisco, CA 94105"
    })
    assert result["success"] is True
    assert "555 Market St" in result["shipping_address"]

def test_update_shipping_address_shipped_rejection():
    """Test that shipping address cannot be changed on already shipped order 1001."""
    result = update_shipping_address.invoke({
        "order_id": 1001,
        "new_address": "555 Market St, San Francisco, CA"
    })
    assert result["success"] is False
    assert result["error"] == "CANNOT_UPDATE_ADDRESS"

# 5. Refund Eligibility & Creation Tests
def test_refund_eligibility_delivered_order():
    """Test refund eligibility for Order 1002 (Delivered 10 days ago, eligible)."""
    result = check_refund_eligibility.invoke({"order_id": 1002})
    assert result["success"] is True
    assert result["eligible"] is True
    assert result["product_name"] == "Headphones"

def test_refund_eligibility_shipped_order():
    """Test refund eligibility for Order 1001 (Shipped, ineligible before delivery)."""
    result = check_refund_eligibility.invoke({"order_id": 1001})
    assert result["success"] is True
    assert result["eligible"] is False
    assert result["reason"] == "ORDER_IN_TRANSIT"

def test_create_refund_request_success():
    """Test creating a refund request for eligible Order 1002."""
    result = create_refund_request.invoke({"order_id": 1002})
    assert result["success"] is True
    assert result["order_id"] == 1002
    assert "ticket_id" in result
    assert result["refund_amount"] == 150.00

# 6. Support Ticket & Human Escalation Tests
def test_create_support_ticket_success():
    """Test generating a standard customer support ticket."""
    result = create_support_ticket.invoke({
        "customer_id": 1,
        "issue": "Need assistance with Bluetooth pairing on headphones."
    })
    assert result["success"] is True
    assert result["status"] == "Open"
    assert "ticket_id" in result

def test_escalate_to_human_agent():
    """Test urgent human escalation workflow."""
    result = escalate_to_human_agent.invoke({
        "customer_id": 1,
        "reason": "Customer tried troubleshooting 5 times and demands live agent.",
        "urgency": "High"
    })
    assert result["success"] is True
    assert result["escalated"] is True
    assert result["status"] == "Escalated"
    assert result["priority"] == "Urgent"
    assert "Senior Human Specialist" in result["assigned_agent"]

# 7. RAG Knowledge Base Tests
def test_rag_knowledge_base_retrieval():
    """Test querying the policy knowledge base."""
    policy_text = query_knowledge_base("What is the return window?")
    assert len(policy_text) > 0
    assert "30" in policy_text or "return" in policy_text.lower()

# 8. FastAPI Client & Multi-Turn Memory Endpoints Tests
client = TestClient(app)

def test_api_health_endpoint():
    """Test GET /health."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

def test_api_multi_turn_conversation_memory():
    """Test conversational memory where Turn 2 references Turn 1 with pronoun 'it'."""
    session_id = "test-mem-thread-101"
    
    # Turn 1: Ask about order 1003
    r1 = client.post("/chat", json={"message": "Where is my order 1003?", "session_id": session_id})
    assert r1.status_code == 200
    assert "1003" in r1.json()["response"]
    assert "Processing" in r1.json()["response"]

    # Turn 2: 'Can you cancel it?' (agent must remember 'it' is 1003)
    r2 = client.post("/chat", json={"message": "Can you cancel it?", "session_id": session_id})
    assert r2.status_code == 200
    assert "1003" in r2.json()["response"]
    assert "cancelled" in r2.json()["response"].lower()

def test_api_compound_reasoning():
    """Test compound reasoning: 'My order 1003 hasn't arrived and I want a refund'."""
    response = client.post("/chat", json={"message": "My order 1003 hasn't arrived and I want a refund."})
    assert response.status_code == 200
    data = response.json()
    assert "1003" in data["response"]
    assert "Processing" in data["response"]
    # Agent explains it has not arrived and offers direct cancellation for full refund
    assert "cancel" in data["response"].lower() or "refund" in data["response"].lower()

def test_api_human_escalation_workflow():
    """Test human escalation request."""
    response = client.post("/chat", json={"message": "I've tried everything and I want a human."})
    assert response.status_code == 200
    data = response.json()
    assert data["escalated"] is True
    assert "human" in data["response"].lower() or "ticket" in data["response"].lower()

def test_api_dashboard_endpoints():
    """Test Agent Dashboard overview, orders, tickets, traces, and reset APIs."""
    # Overview
    r_over = client.get("/api/dashboard/overview")
    assert r_over.status_code == 200
    assert "total_orders" in r_over.json()
    assert "total_tickets" in r_over.json()

    # Orders list
    r_ord = client.get("/api/dashboard/orders")
    assert r_ord.status_code == 200
    assert len(r_ord.json()) >= 4

    # Tickets list
    r_tick = client.get("/api/dashboard/tickets")
    assert r_tick.status_code == 200
    assert len(r_tick.json()) >= 1

    # Traces
    r_tr = client.get("/api/dashboard/traces")
    assert r_tr.status_code == 200

    # Reset
    r_reset = client.post("/api/dashboard/reset")
    assert r_reset.status_code == 200
    assert r_reset.json()["success"] is True
