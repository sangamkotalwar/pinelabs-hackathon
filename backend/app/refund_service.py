import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Invoice, Payment, Refund, InvoiceStatus, PaymentStatus
from app import pinelabs_client

logger = logging.getLogger(__name__)


async def issue_refund(
    db: Session,
    invoice_id: int,
    amount: float = None,
    reason: str = "Refund requested",
) -> dict:
    """Issue a refund for a paid invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return {"success": False, "error": "Invoice not found"}

    if invoice.status != InvoiceStatus.PAID:
        return {"success": False, "error": f"Invoice is not paid (status: {invoice.status.value})"}

    payment = (
        db.query(Payment)
        .filter(Payment.invoice_id == invoice_id, Payment.status == PaymentStatus.SUCCESS)
        .order_by(Payment.created_at.desc())
        .first()
    )
    if not payment:
        return {"success": False, "error": "No successful payment found for this invoice"}

    refund_amount = amount or invoice.amount
    refund_paise = int(round(refund_amount * 100))

    pinelabs_result = None
    pinelabs_refund_id = None

    if payment.pinelabs_order_id:
        pinelabs_result = await pinelabs_client.initiate_refund(
            order_id=payment.pinelabs_order_id,
            merchant_order_reference=payment.merchant_order_reference,
            amount_paise=refund_paise,
            reason=reason,
        )
        if pinelabs_result.get("success"):
            pinelabs_refund_id = (
                pinelabs_result.get("data", {}).get("refund_id")
                or pinelabs_result.get("data", {}).get("id")
            )

    refund = Refund(
        invoice_id=invoice_id,
        payment_id=payment.id,
        pinelabs_refund_id=pinelabs_refund_id,
        amount=refund_amount,
        reason=reason,
        status="processing" if pinelabs_result and pinelabs_result.get("success") else "initiated",
        processed_at=datetime.utcnow() if not payment.pinelabs_order_id else None,
    )
    db.add(refund)

    invoice.status = InvoiceStatus.REFUNDED
    payment.status = PaymentStatus.REFUNDED

    db.commit()
    db.refresh(refund)

    return {
        "success": True,
        "refund_id": refund.id,
        "invoice_id": invoice_id,
        "invoice_number": invoice.invoice_number,
        "amount": refund_amount,
        "status": refund.status,
        "pinelabs_result": pinelabs_result,
    }
