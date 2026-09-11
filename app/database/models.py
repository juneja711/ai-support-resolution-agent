from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)

    # Relationships
    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    tickets = relationship("SupportTicket", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.name}', email='{self.email}')>"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    product_name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    status = Column(String, nullable=False)  # 'Shipped', 'Delivered', 'Processing', 'Cancelled'
    shipping_address = Column(String, default="123 Innovation Way, Tech City, CA 94016")
    order_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    customer = relationship("Customer", back_populates="orders")

    def __repr__(self):
        return f"<Order(id={self.id}, product='{self.product_name}', status='{self.status}', price={self.price})>"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    issue = Column(Text, nullable=False)
    status = Column(String, default="Open")  # 'Open', 'In Progress', 'Resolved', 'Escalated'
    priority = Column(String, default="Normal")  # 'Low', 'Normal', 'High', 'Urgent'
    assigned_agent = Column(String, default="AI Automated Support")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    customer = relationship("Customer", back_populates="tickets")

    def __repr__(self):
        return f"<SupportTicket(id={self.id}, customer_id={self.customer_id}, status='{self.status}', priority='{self.priority}')>"
