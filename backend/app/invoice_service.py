import uuid
import json
import logging
import os
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models import Invoice, Merchant, InvoiceStatus
from app import pinelabs_client
from app import bedrock_client

logger = logging.getLogger(__name__)

INVOICES_DIR = os.getenv("INVOICES_DIR", "/tmp/paychat_invoices")
os.makedirs(INVOICES_DIR, exist_ok=True)


def generate_invoice_number() -> str:
    return f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


async def create_invoice_from_image(
    db: Session,
    sender_merchant_id: int,
    receiver_merchant_id: int,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    amount_override: Optional[float] = None,
    notes: Optional[str] = None,
) -> Invoice:
    """Parse an uploaded invoice image with Bedrock and create a DB record."""
    parsed = await bedrock_client.parse_invoice_image(image_bytes, mime_type)

    amount = amount_override
    if not amount and parsed:
        amount = parsed.get("total_amount") or 0.0

    invoice_number = generate_invoice_number()
    if parsed and parsed.get("invoice_number"):
        invoice_number = parsed["invoice_number"]
        existing = db.query(Invoice).filter_by(invoice_number=invoice_number).first()
        if existing:
            invoice_number = generate_invoice_number()

    filename = f"{invoice_number.replace('/', '_')}_{uuid.uuid4().hex[:8]}.jpg"
    filepath = os.path.join(INVOICES_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    invoice = Invoice(
        invoice_number=invoice_number,
        sender_merchant_id=sender_merchant_id,
        receiver_merchant_id=receiver_merchant_id,
        amount=amount,
        description=parsed.get("notes") if parsed else notes,
        line_items=json.dumps(parsed.get("line_items", [])) if parsed else "[]",
        status=InvoiceStatus.PENDING,
        raw_image_path=filepath,
        parsed_data=json.dumps(parsed) if parsed else None,
        notes=notes,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def create_invoice_manual(
    db: Session,
    sender_merchant_id: int,
    receiver_merchant_id: int,
    amount: float,
    description: str = "",
    line_items: Optional[List[dict]] = None,
    notes: Optional[str] = None,
) -> Invoice:
    """Create an invoice manually without image."""
    invoice = Invoice(
        invoice_number=generate_invoice_number(),
        sender_merchant_id=sender_merchant_id,
        receiver_merchant_id=receiver_merchant_id,
        amount=amount,
        description=description,
        line_items=json.dumps(line_items or []),
        status=InvoiceStatus.PENDING,
        notes=notes,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def get_pending_invoices_for_merchant(db: Session, merchant_id: int) -> List[Invoice]:
    """Get all pending invoices where this merchant is the receiver (owes money)."""
    return (
        db.query(Invoice)
        .filter(
            Invoice.receiver_merchant_id == merchant_id,
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PAYMENT_LINK_SENT]),
        )
        .order_by(Invoice.created_at.desc())
        .all()
    )


def get_sent_invoices_for_merchant(db: Session, merchant_id: int) -> List[Invoice]:
    """Get invoices sent by this merchant."""
    return (
        db.query(Invoice)
        .filter(Invoice.sender_merchant_id == merchant_id)
        .order_by(Invoice.created_at.desc())
        .all()
    )


def get_invoice_by_id(db: Session, invoice_id: int) -> Optional[Invoice]:
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()


def get_invoice_by_number(db: Session, invoice_number: str) -> Optional[Invoice]:
    return db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()


def get_balance_summary(db: Session, merchant_id: int) -> dict:
    """
    Returns net balance: how much this merchant owes vs is owed.
    payable = sum of amounts in invoices where merchant is receiver and status is pending/link_sent
    receivable = sum of amounts in invoices where merchant is sender and status is pending/link_sent
    """
    pending_statuses = [InvoiceStatus.PENDING, InvoiceStatus.PAYMENT_LINK_SENT]

    payable_invoices = (
        db.query(Invoice)
        .filter(Invoice.receiver_merchant_id == merchant_id, Invoice.status.in_(pending_statuses))
        .all()
    )

    receivable_invoices = (
        db.query(Invoice)
        .filter(Invoice.sender_merchant_id == merchant_id, Invoice.status.in_(pending_statuses))
        .all()
    )

    total_payable = sum(inv.amount for inv in payable_invoices)
    total_receivable = sum(inv.amount for inv in receivable_invoices)

    return {
        "total_payable": total_payable,
        "total_receivable": total_receivable,
        "net": total_receivable - total_payable,
        "payable_count": len(payable_invoices),
        "receivable_count": len(receivable_invoices),
    }
