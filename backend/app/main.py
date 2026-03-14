import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional, List

from dotenv import load_dotenv
load_dotenv()

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import Merchant, Invoice, Payment, Refund, InvoiceStatus, PaymentStatus
from app import invoice_service, payment_service, refund_service, webhook_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BOT_ENABLED = os.getenv("TELEGRAM_BOT_TOKEN", "") != ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("PayChat database initialized.")

    bot_task = None
    if BOT_ENABLED:
        try:
            from app.telegram_bot import build_application
            bot_app = build_application()
            await bot_app.initialize()
            await bot_app.start()
            await bot_app.updater.start_polling()
            logger.info("Telegram bot started (long-polling).")
            app.state.bot_app = bot_app
            bot_task = asyncio.current_task()
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")

    yield

    if BOT_ENABLED and hasattr(app.state, "bot_app"):
        try:
            await app.state.bot_app.updater.stop()
            await app.state.bot_app.stop()
            await app.state.bot_app.shutdown()
            logger.info("Telegram bot stopped.")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")


app = FastAPI(
    title="PayChat API",
    description="B2B Telegram payment system powered by Pine Labs",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic Schemas ──────────────────────────────────────────────────────────

class MerchantCreate(BaseModel):
    telegram_chat_id: str
    business_name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class InvoiceCreate(BaseModel):
    sender_chat_id: str
    receiver_chat_id: str
    amount: float
    description: Optional[str] = ""
    line_items: Optional[List[dict]] = []
    notes: Optional[str] = None


class WebhookPayload(BaseModel):
    order_id: Optional[str] = None
    payment_link_id: Optional[str] = None
    merchant_order_reference: Optional[str] = None
    transaction_id: Optional[str] = None
    status: str = "success"
    amount: Optional[float] = None
    currency: Optional[str] = "INR"
    
    # Plural webhook fields
    event_name: Optional[str] = None
    merchant_response: Optional[dict] = None


class RefundRequest(BaseModel):
    invoice_id: int
    amount: Optional[float] = None
    reason: Optional[str] = "Refund requested"


class ResendLinkRequest(BaseModel):
    invoice_id: int


# ─── Merchant Endpoints ────────────────────────────────────────────────────────

@app.post("/merchant/register", tags=["Merchants"])
async def register_merchant(payload: MerchantCreate, db: Session = Depends(get_db)):
    existing = db.query(Merchant).filter_by(telegram_chat_id=payload.telegram_chat_id).first()
    if existing:
        existing.business_name = payload.business_name
        existing.email = payload.email
        existing.phone = payload.phone
        db.commit()
        db.refresh(existing)
        return {"message": "Merchant updated", "merchant_id": existing.id}

    merchant = Merchant(
        telegram_chat_id=payload.telegram_chat_id,
        business_name=payload.business_name,
        email=payload.email,
        phone=payload.phone,
    )
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return {"message": "Merchant registered", "merchant_id": merchant.id}


@app.get("/merchant/{chat_id}", tags=["Merchants"])
async def get_merchant(chat_id: str, db: Session = Depends(get_db)):
    merchant = db.query(Merchant).filter_by(telegram_chat_id=chat_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return {
        "id": merchant.id,
        "telegram_chat_id": merchant.telegram_chat_id,
        "business_name": merchant.business_name,
        "email": merchant.email,
        "phone": merchant.phone,
        "created_at": merchant.created_at.isoformat(),
    }


@app.get("/merchants", tags=["Merchants"])
async def list_merchants(db: Session = Depends(get_db)):
    merchants = db.query(Merchant).all()
    return [
        {
            "id": m.id,
            "telegram_chat_id": m.telegram_chat_id,
            "business_name": m.business_name,
            "email": m.email,
        }
        for m in merchants
    ]


# ─── Invoice Endpoints ─────────────────────────────────────────────────────────

@app.post("/invoice/create", tags=["Invoices"])
async def create_invoice(
    payload: InvoiceCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    sender = db.query(Merchant).filter_by(telegram_chat_id=payload.sender_chat_id).first()
    receiver = db.query(Merchant).filter_by(telegram_chat_id=payload.receiver_chat_id).first()

    if not sender:
        raise HTTPException(status_code=404, detail=f"Sender merchant not found: {payload.sender_chat_id}")
    if not receiver:
        raise HTTPException(status_code=404, detail=f"Receiver merchant not found: {payload.receiver_chat_id}")

    inv = invoice_service.create_invoice_manual(
        db=db,
        sender_merchant_id=sender.id,
        receiver_merchant_id=receiver.id,
        amount=payload.amount,
        description=payload.description,
        line_items=payload.line_items,
        notes=payload.notes,
    )

    result = await payment_service.generate_payment_link(db, inv.id)

    background_tasks.add_task(
        webhook_service.send_payment_request_notification,
        receiver_chat_id=payload.receiver_chat_id,
        sender_business_name=sender.business_name,
        invoice_number=inv.invoice_number,
        amount=payload.amount,
        payment_link=result.get("payment_link", ""),
    )

    return {
        "invoice_id": inv.id,
        "invoice_number": inv.invoice_number,
        "amount": inv.amount,
        "status": inv.status.value,
        "payment_link": result.get("payment_link"),
    }


@app.post("/invoice/upload", tags=["Invoices"])
async def upload_invoice(
    sender_chat_id: str = Form(...),
    receiver_chat_id: str = Form(...),
    amount_override: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    sender = db.query(Merchant).filter_by(telegram_chat_id=sender_chat_id).first()
    receiver = db.query(Merchant).filter_by(telegram_chat_id=receiver_chat_id).first()

    if not sender:
        raise HTTPException(status_code=404, detail="Sender merchant not found")
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver merchant not found")

    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    inv = await invoice_service.create_invoice_from_image(
        db=db,
        sender_merchant_id=sender.id,
        receiver_merchant_id=receiver.id,
        image_bytes=image_bytes,
        mime_type=mime_type,
        amount_override=amount_override,
        notes=notes,
    )

    result = await payment_service.generate_payment_link(db, inv.id)

    background_tasks.add_task(
        webhook_service.send_payment_request_notification,
        receiver_chat_id=receiver_chat_id,
        sender_business_name=sender.business_name,
        invoice_number=inv.invoice_number,
        amount=inv.amount,
        payment_link=result.get("payment_link", ""),
    )

    return {
        "invoice_id": inv.id,
        "invoice_number": inv.invoice_number,
        "amount": inv.amount,
        "status": inv.status.value,
        "payment_link": result.get("payment_link"),
        "parsed_data": inv.parsed_data,
    }


@app.get("/invoice/pending", tags=["Invoices"])
async def get_pending_invoices(chat_id: str, db: Session = Depends(get_db)):
    merchant = db.query(Merchant).filter_by(telegram_chat_id=chat_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    invoices = invoice_service.get_pending_invoices_for_merchant(db, merchant.id)
    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "from_business": inv.sender.business_name if inv.sender else None,
            "amount": inv.amount,
            "status": inv.status.value,
            "payment_link": inv.payment_link,
            "created_at": inv.created_at.isoformat(),
        }
        for inv in invoices
    ]


@app.get("/invoice/sent", tags=["Invoices"])
async def get_sent_invoices(chat_id: str, db: Session = Depends(get_db)):
    merchant = db.query(Merchant).filter_by(telegram_chat_id=chat_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    invoices = invoice_service.get_sent_invoices_for_merchant(db, merchant.id)
    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "to_business": inv.receiver.business_name if inv.receiver else None,
            "amount": inv.amount,
            "status": inv.status.value,
            "payment_link": inv.payment_link,
            "created_at": inv.created_at.isoformat(),
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        }
        for inv in invoices
    ]


@app.get("/invoice/{invoice_id}", tags=["Invoices"])
async def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    inv = invoice_service.get_invoice_by_id(db, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "sender": inv.sender.business_name if inv.sender else None,
        "receiver": inv.receiver.business_name if inv.receiver else None,
        "amount": inv.amount,
        "description": inv.description,
        "line_items": inv.line_items,
        "status": inv.status.value,
        "payment_link": inv.payment_link,
        "created_at": inv.created_at.isoformat(),
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
    }


@app.get("/invoice/balance/{chat_id}", tags=["Invoices"])
async def get_balance(chat_id: str, db: Session = Depends(get_db)):
    merchant = db.query(Merchant).filter_by(telegram_chat_id=chat_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    return {
        "merchant": merchant.business_name,
        **invoice_service.get_balance_summary(db, merchant.id),
    }


# ─── Payment Endpoints ─────────────────────────────────────────────────────────

@app.post("/payment/webhook", tags=["Payments"])
async def payment_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Handle payment webhooks from Plural/Pine Labs."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    # Ignore empty webhooks (likely from browser/health checks)
    if not body:
        logger.debug("Received empty webhook request, ignoring")
        return {"success": True, "message": "Empty request ignored"}
    
    logger.info(f"Received payment webhook: {body}")
    
    # Try to extract fields from various possible formats
    event_type = body.get("event_type") or body.get("event_name") or body.get("event")
    data = body.get("data") or body.get("merchant_response") or body
    
    # Determine status from event type or data fields
    status = "pending"
    event_type_lower = str(event_type).lower() if event_type else ""
    data_status_lower = str(data.get("status", "")).lower()
    
    # Check event type for success indicators
    if "processed" in event_type_lower or "captured" in event_type_lower or "completion" in event_type_lower or "success" in event_type_lower:
        status = "success"
    elif "failed" in event_type_lower or "failure" in event_type_lower:
        status = "failed"
    # Check data.status for success indicators
    elif data_status_lower in ("success", "paid", "captured", "completed", "processed"):
        status = "success"
    # Check for Pine Labs specific fields
    elif data.get("pine_pg_txn_status") == "4" or data.get("txn_response_code") == "1":
        status = "success"
    # Check payments array for processed status
    elif data.get("payments"):
        payments = data.get("payments", [])
        if any(str(p.get("status", "")).lower() == "processed" for p in payments):
            status = "success"
    
    # Extract identifiers - prioritize merchant_payment_link_reference (our PAYCHAT reference)
    merchant_order_ref = (
        data.get("merchant_payment_link_reference")
        or data.get("unique_merchant_txn_id")
        or data.get("merchant_order_reference")
        or body.get("merchant_payment_link_reference")
        or body.get("merchant_order_reference")
    )
    
    # Extract transaction ID from payments array if available
    transaction_id = None
    if data.get("payments"):
        payments = data.get("payments", [])
        if payments:
            transaction_id = payments[0].get("id") or payments[0].get("acquirer_data", {}).get("rrn")
    if not transaction_id:
        transaction_id = (
            data.get("pine_pg_transaction_id")
            or data.get("txn_id")
            or data.get("transaction_id")
            or body.get("transaction_id")
            or body.get("txn_id")
        )
    
    order_id = data.get("order_id") or body.get("order_id")
    payment_link_id = data.get("payment_link_id") or body.get("payment_link_id")
    
    logger.info(f"Parsed webhook: status={status}, merchant_ref={merchant_order_ref}, order_id={order_id}, payment_link_id={payment_link_id}, txn_id={transaction_id}")
    
    result = await payment_service.process_payment_webhook(
        db=db,
        order_id=order_id,
        payment_link_id=payment_link_id,
        merchant_order_reference=merchant_order_ref,
        transaction_id=transaction_id,
        status=status,
    )

    if result.get("success") and result.get("invoice_id"):
        inv = invoice_service.get_invoice_by_id(db, result["invoice_id"])
        if inv and inv.sender and inv.receiver:
            background_tasks.add_task(
                webhook_service.send_payment_confirmation,
                sender_chat_id=inv.sender.telegram_chat_id,
                receiver_chat_id=inv.receiver.telegram_chat_id,
                sender_business_name=inv.sender.business_name,
                receiver_business_name=inv.receiver.business_name,
                invoice_number=inv.invoice_number,
                amount=inv.amount,
            )

    return result


@app.post("/payment/webhook/raw", tags=["Payments"])
async def payment_webhook_raw(
    request_body: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Raw webhook endpoint that accepts any JSON payload from Plural."""
    logger.info(f"Received raw payment webhook: {request_body}")
    
    # Try to extract relevant fields from various possible formats
    event_name = request_body.get("event_name") or request_body.get("event")
    merchant_response = request_body.get("merchant_response") or request_body.get("data") or request_body
    
    # Determine status
    status = "pending"
    if event_name:
        if "captured" in event_name or "completion" in event_name or "success" in event_name:
            status = "success"
        elif "failed" in event_name:
            status = "failed"
    elif merchant_response.get("pine_pg_txn_status") == "4" or merchant_response.get("txn_response_code") == "1":
        status = "success"
    elif merchant_response.get("status", "").lower() in ("success", "paid", "captured"):
        status = "success"
    
    # Extract identifiers
    merchant_order_ref = (
        merchant_response.get("unique_merchant_txn_id")
        or merchant_response.get("merchant_order_reference")
        or merchant_response.get("merchant_payment_link_reference")
    )
    transaction_id = (
        merchant_response.get("pine_pg_transaction_id")
        or merchant_response.get("txn_id")
        or merchant_response.get("transaction_id")
    )
    order_id = merchant_response.get("order_id")
    payment_link_id = merchant_response.get("payment_link_id")
    
    logger.info(f"Parsed webhook: status={status}, merchant_ref={merchant_order_ref}, txn_id={transaction_id}")
    
    result = await payment_service.process_payment_webhook(
        db=db,
        order_id=order_id,
        payment_link_id=payment_link_id,
        merchant_order_reference=merchant_order_ref,
        transaction_id=transaction_id,
        status=status,
    )
    
    if result.get("success") and result.get("invoice_id"):
        inv = invoice_service.get_invoice_by_id(db, result["invoice_id"])
        if inv and inv.sender and inv.receiver:
            background_tasks.add_task(
                webhook_service.send_payment_confirmation,
                sender_chat_id=inv.sender.telegram_chat_id,
                receiver_chat_id=inv.receiver.telegram_chat_id,
                sender_business_name=inv.sender.business_name,
                receiver_business_name=inv.receiver.business_name,
                invoice_number=inv.invoice_number,
                amount=inv.amount,
            )
    
    return result


@app.post("/demo/pay/{invoice_reference}", tags=["Demo"])
async def demo_pay(
    invoice_reference: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Demo endpoint to simulate payment success (for hackathon demo)."""
    inv = (
        db.query(Invoice).filter(Invoice.invoice_number == invoice_reference).first()
        or db.query(Invoice).filter(Invoice.id == int(invoice_reference) if invoice_reference.isdigit() else -1).first()
    )

    if not inv:
        payment = db.query(Payment).filter(Payment.merchant_order_reference.contains(invoice_reference)).first()
        if payment:
            inv = payment.invoice

    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    result = await payment_service.process_payment_webhook(
        db=db,
        merchant_order_reference=inv.payment_link.split("/")[-1] if inv.payment_link else None,
        transaction_id=f"DEMO-TXN-{invoice_reference}",
        status="success",
    )

    if not result.get("success"):
        payment = db.query(Payment).filter(
            Payment.invoice_id == inv.id,
            Payment.status == PaymentStatus.CREATED,
        ).first()
        if payment:
            result = await payment_service.process_payment_webhook(
                db=db,
                merchant_order_reference=payment.merchant_order_reference,
                transaction_id=f"DEMO-TXN-{invoice_reference}",
                status="success",
            )

    if result.get("success") and inv.sender and inv.receiver:
        background_tasks.add_task(
            webhook_service.send_payment_confirmation,
            sender_chat_id=inv.sender.telegram_chat_id,
            receiver_chat_id=inv.receiver.telegram_chat_id,
            sender_business_name=inv.sender.business_name,
            receiver_business_name=inv.receiver.business_name,
            invoice_number=inv.invoice_number,
            amount=inv.amount,
        )

    return {
        "message": "Demo payment processed",
        "invoice_number": inv.invoice_number,
        "amount": inv.amount,
        "result": result,
    }


@app.get("/demo/pay/{invoice_reference}", tags=["Demo"], response_class=HTMLResponse)
async def demo_pay_page(invoice_reference: str, db: Session = Depends(get_db)):
    """Demo payment page rendered as HTML."""
    inv = (
        db.query(Invoice).filter(Invoice.invoice_number == invoice_reference).first()
        or db.query(Invoice).filter(Invoice.id == int(invoice_reference) if invoice_reference.isdigit() else -1).first()
    )

    if not inv:
        return HTMLResponse("<h1>Invoice Not Found</h1>", status_code=404)

    status_badge = ""
    pay_button = ""
    if inv.status == InvoiceStatus.PAID:
        status_badge = '<span style="color:green;font-size:2em;">✅ PAID</span>'
    else:
        status_badge = f'<span style="color:orange;font-size:1.5em;">⏳ {inv.status.value.upper()}</span>'
        pay_button = f"""
        <form method="post" action="/demo/pay/{invoice_reference}" style="margin-top:20px">
            <button type="submit" style="
                background:#4CAF50;color:white;padding:15px 40px;
                font-size:1.2em;border:none;border-radius:8px;cursor:pointer;">
                💳 Pay ₹{inv.amount:,.2f}
            </button>
        </form>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PayChat - Pay Invoice</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; }}
            .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; color: #1a73e8; margin-bottom: 20px; }}
            .row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }}
            .amount {{ font-size: 2em; font-weight: bold; color: #333; text-align: center; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header"><h2>💳 PayChat Invoice</h2></div>
            <div class="row"><span>Invoice #</span><strong>{inv.invoice_number}</strong></div>
            <div class="row"><span>From</span><strong>{inv.sender.business_name if inv.sender else 'N/A'}</strong></div>
            <div class="row"><span>To</span><strong>{inv.receiver.business_name if inv.receiver else 'N/A'}</strong></div>
            <div class="row"><span>Description</span><span>{inv.description or 'Invoice Payment'}</span></div>
            <div class="row"><span>Date</span><span>{inv.created_at.strftime('%d %b %Y')}</span></div>
            <div class="amount">₹{inv.amount:,.2f}</div>
            <div style="text-align:center">{status_badge}</div>
            {pay_button}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)


# ─── Refund Endpoints ──────────────────────────────────────────────────────────

@app.post("/invoice/refund", tags=["Refunds"])
async def refund_invoice(
    payload: RefundRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    result = await refund_service.issue_refund(
        db=db,
        invoice_id=payload.invoice_id,
        amount=payload.amount,
        reason=payload.reason,
    )

    if result.get("success"):
        inv = invoice_service.get_invoice_by_id(db, payload.invoice_id)
        if inv and inv.sender and inv.receiver:
            background_tasks.add_task(
                webhook_service.send_refund_notification,
                sender_chat_id=inv.sender.telegram_chat_id,
                receiver_chat_id=inv.receiver.telegram_chat_id,
                invoice_number=inv.invoice_number,
                amount=result["amount"],
                reason=payload.reason,
            )

    return result


@app.post("/payment/resend", tags=["Payments"])
async def resend_payment_link(
    payload: ResendLinkRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    inv = invoice_service.get_invoice_by_id(db, payload.invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if inv.status == InvoiceStatus.PAID:
        return {"success": False, "message": "Invoice already paid"}

    if not inv.payment_link:
        result = await payment_service.generate_payment_link(db, inv.id)
        payment_link = result.get("payment_link", "")
    else:
        payment_link = inv.payment_link

    if inv.receiver:
        background_tasks.add_task(
            webhook_service.send_payment_request_notification,
            receiver_chat_id=inv.receiver.telegram_chat_id,
            sender_business_name=inv.sender.business_name if inv.sender else "Merchant",
            invoice_number=inv.invoice_number,
            amount=inv.amount,
            payment_link=payment_link,
        )

    return {"success": True, "payment_link": payment_link, "invoice_number": inv.invoice_number}


# ─── Dashboard Endpoints ───────────────────────────────────────────────────────

@app.get("/dashboard/{chat_id}", tags=["Dashboard"])
async def get_dashboard(chat_id: str, db: Session = Depends(get_db)):
    merchant = db.query(Merchant).filter_by(telegram_chat_id=chat_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    balance = invoice_service.get_balance_summary(db, merchant.id)
    recent_sent = invoice_service.get_sent_invoices_for_merchant(db, merchant.id)[:5]
    recent_pending = invoice_service.get_pending_invoices_for_merchant(db, merchant.id)[:5]

    return {
        "merchant": {
            "id": merchant.id,
            "business_name": merchant.business_name,
            "email": merchant.email,
        },
        "balance": balance,
        "recent_sent": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "to": inv.receiver.business_name if inv.receiver else None,
                "amount": inv.amount,
                "status": inv.status.value,
                "created_at": inv.created_at.isoformat(),
            }
            for inv in recent_sent
        ],
        "recent_pending": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "from": inv.sender.business_name if inv.sender else None,
                "amount": inv.amount,
                "status": inv.status.value,
                "payment_link": inv.payment_link,
                "created_at": inv.created_at.isoformat(),
            }
            for inv in recent_pending
        ],
    }


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "PayChat API"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
