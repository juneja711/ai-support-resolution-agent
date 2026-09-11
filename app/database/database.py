from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.database.models import Base, Customer, Order, SupportTicket

# Ensure parent directory for SQLite database exists
db_path = settings.DATABASE_URL.replace("sqlite:///", "")
Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# Create engine for SQLite
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency that yields a database session and closes it afterwards."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def reset_db():
    """Drop all tables, recreate them, and seed fresh sample records."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db: Session = SessionLocal()
    try:
        # 1. Create sample customers
        customer1 = Customer(id=1, name="Alice Johnson", email="alice@example.com")
        customer2 = Customer(id=2, name="Bob Smith", email="bob@example.com")
        db.add_all([customer1, customer2])
        db.commit()

        # 2. Create sample orders
        now = datetime.now(timezone.utc)
        orders = [
            Order(
                id=1001,
                customer_id=1,
                product_name="Laptop",
                price=1200.00,
                status="Shipped",
                shipping_address="742 Evergreen Terrace, Springfield, OR 97477",
                order_date=now - timedelta(days=3)
            ),
            Order(
                id=1002,
                customer_id=1,
                product_name="Headphones",
                price=150.00,
                status="Delivered",
                shipping_address="742 Evergreen Terrace, Springfield, OR 97477",
                order_date=now - timedelta(days=10)
            ),
            Order(
                id=1003,
                customer_id=2,
                product_name="Keyboard",
                price=80.00,
                status="Processing",
                shipping_address="100 Pine Street, Seattle, WA 98101",
                order_date=now - timedelta(days=1)
            ),
            Order(
                id=1004,
                customer_id=2,
                product_name="Mouse",
                price=30.00,
                status="Cancelled",
                shipping_address="100 Pine Street, Seattle, WA 98101",
                order_date=now - timedelta(days=5)
            )
        ]
        db.add_all(orders)

        # 3. Create initial support tickets
        sample_ticket = SupportTicket(
            id=1,
            customer_id=1,
            issue="Initial account setup inquiry",
            status="Resolved",
            priority="Low",
            assigned_agent="AI Automated Support",
            notes="Customer helped with initial login instructions.",
            created_at=now - timedelta(days=15)
        )
        db.add(sample_ticket)
        db.commit()
        print(" Database initialized and seeded with demo records.")
    finally:
        db.close()

def init_db():
    """Initialize database tables and seed if empty."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        if db.query(Customer).count() == 0:
            reset_db()
    finally:
        db.close()
