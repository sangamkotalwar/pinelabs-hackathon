from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PAYMENT_LINK_SENT = "payment_link_sent"
    PAID = "paid"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    telegram_chat_id = Column(String, unique=True, index=True, nullable=False)
    business_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sent_invoices = relationship("Invoice", foreign_keys="Invoice.sender_merchant_id", back_populates="sender")
    received_invoices = relationship("Invoice", foreign_keys="Invoice.receiver_merchant_id", back_populates="receiver")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, unique=True, index=True, nullable=False)
    sender_merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    receiver_merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    line_items = Column(Text, nullable=True)  # JSON string of SKUs
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.PENDING)
    raw_image_path = Column(String, nullable=True)
    parsed_data = Column(Text, nullable=True)  # JSON from Bedrock OCR
    payment_link = Column(String, nullable=True)
    pinelabs_order_id = Column(String, nullable=True)
    pinelabs_payment_link_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    sender = relationship("Merchant", foreign_keys=[sender_merchant_id], back_populates="sent_invoices")
    receiver = relationship("Merchant", foreign_keys=[receiver_merchant_id], back_populates="received_invoices")
    payments = relationship("Payment", back_populates="invoice")
    refunds = relationship("Refund", back_populates="invoice")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    pinelabs_order_id = Column(String, nullable=True, index=True)
    pinelabs_payment_link_id = Column(String, nullable=True)
    merchant_order_reference = Column(String, unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    status = Column(Enum(PaymentStatus), default=PaymentStatus.CREATED)
    payment_link_url = Column(String, nullable=True)
    transaction_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    metadata_json = Column(Text, nullable=True)

    invoice = relationship("Invoice", back_populates="payments")
    refunds = relationship("Refund", back_populates="payment")


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    pinelabs_refund_id = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String, default="initiated")
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    invoice = relationship("Invoice", back_populates="refunds")
    payment = relationship("Payment", back_populates="refunds")
