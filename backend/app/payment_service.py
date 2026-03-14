import uuid
import logging
import os
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models import Invoice, Payment, Merchant, InvoiceStatus, PaymentStatus
from app import pinelabs_client

logger = logging.getLogger(__name__)

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://nonsentiently-wonderless-elanor.ngrok-free.dev")


def _rupees_to_paise(amount_rupees: float) -> int:
    return int(round(amount_rupees * 100))


async def generate_payment_link(
    db: Session,
    invoice_id: int,
) -> dict:
    """Generate a Pine Labs payment link for an invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return {"success": False, "error": "Invoice not found"}

    if invoice.status == InvoiceStatus.PAID:
        return {"success": False, "error": "Invoice already paid"}

    merchant_order_ref = f"PAYCHAT-{invoice.invoice_number}-{uuid.uuid4().hex[:8]}"
    amount_paise = _rupees_to_paise(invoice.amount)

    receiver: Merchant = invoice.receiver
    customer_name = receiver.business_name if receiver else "Customer"
    customer_email = receiver.email if receiver else None
    customer_mobile = receiver.phone if receiver else None

    result = await pinelabs_client.create_payment_link(
        merchant_order_reference=merchant_order_ref,
        amount_paise=amount_paise,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_mobile=customer_mobile,
        description=f"Invoice {invoice.invoice_number} - {invoice.description or ''}",
    )

    if result.get("success"):
        link_data = result["data"]
        payment_link_url = (
            link_data.get("payment_link")
            or link_data.get("redirect_url")
            or link_data.get("payment_link_url")
            or link_data.get("short_url")
            or f"{APP_BASE_URL}/demo/pay/{invoice.invoice_number}"
        )
        pinelabs_id = link_data.get("payment_link_id") or link_data.get("id")
        logger.info(f"Payment link URL extracted: {payment_link_url}")
    else:
        payment_link_url = result.get("fallback_url") or f"{APP_BASE_URL}/demo/pay/{invoice.invoice_number}"
        pinelabs_id = None
        logger.warning(f"Using demo payment link for invoice {invoice.invoice_number}")

    payment = Payment(
        invoice_id=invoice.id,
        pinelabs_payment_link_id=pinelabs_id,
        merchant_order_reference=merchant_order_ref,
        amount=invoice.amount,
        currency="INR",
        status=PaymentStatus.CREATED,
        payment_link_url=payment_link_url,
    )
    db.add(payment)

    invoice.status = InvoiceStatus.PAYMENT_LINK_SENT
    invoice.payment_link = payment_link_url
    invoice.pinelabs_payment_link_id = pinelabs_id

    db.commit()
    db.refresh(payment)

    return {
        "success": True,
        "payment_id": payment.id,
        "payment_link": payment_link_url,
        "merchant_order_reference": merchant_order_ref,
        "amount": invoice.amount,
        "invoice_number": invoice.invoice_number,
    }


async def process_payment_webhook(
    db: Session,
    order_id: Optional[str] = None,
    payment_link_id: Optional[str] = None,
    merchant_order_reference: Optional[str] = None,
    transaction_id: Optional[str] = None,
    status: str = "success",
) -> dict:
    """Process an incoming payment webhook from Pine Labs or demo endpoint."""
    payment = None
    
    logger.info(f"Processing webhook: order_id={order_id}, payment_link_id={payment_link_id}, merchant_ref={merchant_order_reference}, status={status}")

    # Try payment_link_id first (most reliable for Plural webhooks)
    if payment_link_id:
        payment = db.query(Payment).filter(Payment.pinelabs_payment_link_id == payment_link_id).first()
        if payment:
            logger.info(f"Found payment by payment_link_id: {payment_link_id}")
    
    # Try merchant_order_reference (our PAYCHAT- reference)
    if not payment and merchant_order_reference:
        payment = db.query(Payment).filter(Payment.merchant_order_reference == merchant_order_reference).first()
        if payment:
            logger.info(f"Found payment by merchant_order_reference: {merchant_order_reference}")
    
    # Try order_id
    if not payment and order_id:
        payment = db.query(Payment).filter(Payment.pinelabs_order_id == order_id).first()
        if payment:
            logger.info(f"Found payment by order_id: {order_id}")
    
    # Try matching by invoice number extracted from PAYCHAT reference
    if not payment and merchant_order_reference and merchant_order_reference.startswith("PAYCHAT-"):
        parts = merchant_order_reference.split("-")
        if len(parts) >= 4:
            invoice_num = "-".join(parts[1:4])  # e.g., INV-20260314-6EF9F7
            invoice = db.query(Invoice).filter(Invoice.invoice_number == invoice_num).first()
            if invoice:
                payment = db.query(Payment).filter(
                    Payment.invoice_id == invoice.id
                ).order_by(Payment.created_at.desc()).first()
                if payment:
                    logger.info(f"Found payment by invoice number: {invoice_num}")

    if not payment:
        logger.warning(f"Payment record not found for: order_id={order_id}, payment_link_id={payment_link_id}, merchant_ref={merchant_order_reference}")
        return {"success": False, "error": "Payment record not found"}
    
    logger.info(f"Found payment id={payment.id}, current status={payment.status}")

    if payment.status == PaymentStatus.SUCCESS:
        logger.info(f"Payment {payment.id} already processed, skipping")
        invoice = payment.invoice
        return {
            "success": True, 
            "message": "Payment already processed", 
            "payment_id": payment.id,
            "invoice_id": invoice.id if invoice else None,
            "invoice_number": invoice.invoice_number if invoice else None,
        }

    if status.lower() in ("success", "paid", "captured"):
        payment.status = PaymentStatus.SUCCESS
        payment.paid_at = datetime.utcnow()
        payment.transaction_id = transaction_id or order_id

        invoice = payment.invoice
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.utcnow()

        db.commit()
        return {
            "success": True,
            "payment_id": payment.id,
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "amount": payment.amount,
            "sender_merchant_id": invoice.sender_merchant_id,
            "receiver_merchant_id": invoice.receiver_merchant_id,
        }
    else:
        payment.status = PaymentStatus.FAILED
        db.commit()
        return {"success": False, "error": f"Payment status: {status}"}


def get_payment_by_invoice(db: Session, invoice_id: int) -> Optional[Payment]:
    return (
        db.query(Payment)
        .filter(Payment.invoice_id == invoice_id, Payment.status.in_([PaymentStatus.CREATED, PaymentStatus.SUCCESS]))
        .order_by(Payment.created_at.desc())
        .first()
    )
