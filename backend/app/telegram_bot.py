"""
Telegram bot handler for PayChat.
Uses long-polling via python-telegram-bot library.
"""
import logging
import os
import io
from typing import Optional
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Merchant, Invoice, InvoiceStatus
from app import invoice_service, payment_service, refund_service, webhook_service

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# In-memory state tracking for multi-step flows
user_state: dict = {}


def get_db() -> Session:
    return SessionLocal()


def get_or_create_merchant(db: Session, chat_id: str, username: str = None) -> Merchant:
    merchant = db.query(Merchant).filter_by(telegram_chat_id=chat_id).first()
    if not merchant:
        business_name = username or f"Business_{chat_id[-4:]}"
        merchant = Merchant(
            telegram_chat_id=chat_id,
            business_name=business_name,
        )
        db.add(merchant)
        db.commit()
        db.refresh(merchant)
    return merchant


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_db()
    try:
        chat_id = str(update.effective_chat.id)
        username = update.effective_user.username or update.effective_user.first_name
        merchant = get_or_create_merchant(db, chat_id, username)

        text = (
            f"👋 Welcome to <b>PayChat</b>!\n\n"
            f"Your business: <b>{merchant.business_name}</b>\n\n"
            f"<b>Available Commands:</b>\n"
            f"📤 /invoice — Upload or create an invoice\n"
            f"📋 /pending — View pending payments\n"
            f"🔄 /refund — Issue a refund\n"
            f"📊 /balance — View your balance summary\n"
            f"ℹ️ /register — Update your business profile\n\n"
            f"Upload an invoice image to get started!"
        )
        await update.message.reply_html(text)
    finally:
        db.close()


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    args = context.args

    if not args:
        await update.message.reply_html(
            "📝 <b>Register your business</b>\n\n"
            "Usage: <code>/register BusinessName [email] [phone]</code>\n"
            "Example: <code>/register Acme Corp acme@example.com 9876543210</code>"
        )
        return

    db = get_db()
    try:
        merchant = get_or_create_merchant(db, chat_id)
        merchant.business_name = args[0]
        if len(args) > 1:
            merchant.email = args[1]
        if len(args) > 2:
            merchant.phone = args[2]
        db.commit()

        await update.message.reply_html(
            f"✅ Business registered!\n"
            f"<b>Name:</b> {merchant.business_name}\n"
            f"<b>Email:</b> {merchant.email or 'Not set'}\n"
            f"<b>Phone:</b> {merchant.phone or 'Not set'}"
        )
    finally:
        db.close()


async def cmd_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    args = context.args

    if not args:
        text = (
            "📤 <b>Create Invoice</b>\n\n"
            "<b>Option 1:</b> Upload an invoice image (photo/document)\n"
            "I'll automatically read the details using AI.\n\n"
            "<b>Option 2:</b> Manual entry:\n"
            "<code>/invoice &lt;vendor_chat_id&gt; &lt;amount&gt; [description]</code>\n"
            "Example: <code>/invoice 123456789 1500 Office supplies</code>\n\n"
            "To find someone's chat ID, ask them to use /start and share their ID."
        )
        user_state[chat_id] = {"action": "awaiting_invoice_image"}
        await update.message.reply_html(text)
        return

    if len(args) < 2:
        await update.message.reply_text("Usage: /invoice <vendor_chat_id> <amount> [description]")
        return

    db = get_db()
    try:
        receiver_chat_id = args[0]
        amount = float(args[1])
        description = " ".join(args[2:]) if len(args) > 2 else "Invoice"

        sender = get_or_create_merchant(db, chat_id)
        receiver = db.query(Merchant).filter_by(telegram_chat_id=receiver_chat_id).first()

        if not receiver:
            await update.message.reply_html(
                f"❌ No business found with chat ID <code>{receiver_chat_id}</code>.\n"
                f"Ask them to start the bot first with /start."
            )
            return

        inv = invoice_service.create_invoice_manual(
            db=db,
            sender_merchant_id=sender.id,
            receiver_merchant_id=receiver.id,
            amount=amount,
            description=description,
        )

        result = await payment_service.generate_payment_link(db, inv.id)
        payment_link = result.get("payment_link", "")

        await update.message.reply_html(
            f"✅ <b>Invoice Created!</b>\n\n"
            f"📄 <b>Invoice:</b> {inv.invoice_number}\n"
            f"💵 <b>Amount:</b> ₹{amount:,.2f}\n"
            f"📋 <b>Description:</b> {description}\n"
            f"🔗 <b>Payment Link:</b> <a href=\"{payment_link}\">Pay Now</a>\n\n"
            f"Notification sent to {receiver.business_name}."
        )

        await webhook_service.send_payment_request_notification(
            receiver_chat_id=receiver_chat_id,
            sender_business_name=sender.business_name,
            invoice_number=inv.invoice_number,
            amount=amount,
            payment_link=payment_link,
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a number.")
    finally:
        db.close()


async def handle_document_or_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle uploaded invoice images or documents."""
    chat_id = str(update.effective_chat.id)
    db = get_db()

    try:
        file = None
        mime_type = "image/jpeg"

        if update.message.photo:
            file_obj = update.message.photo[-1]
            file = await context.bot.get_file(file_obj.file_id)
        elif update.message.document:
            doc = update.message.document
            mime_type = doc.mime_type or "image/jpeg"
            if not mime_type.startswith("image/") and mime_type != "application/pdf":
                await update.message.reply_text("❌ Please upload an image (JPG/PNG) or PDF invoice.")
                return
            file = await context.bot.get_file(doc.file_id)

        if not file:
            return

        await update.message.reply_text("🔍 Reading your invoice with AI... please wait.")

        file_bytes = await file.download_as_bytearray()
        image_bytes = bytes(file_bytes)

        sender = get_or_create_merchant(db, chat_id)

        state = user_state.get(chat_id, {})
        if state.get("receiver_merchant_id"):
            receiver_id = state["receiver_merchant_id"]
            user_state.pop(chat_id, None)
        else:
            await update.message.reply_html(
                "📤 Invoice image received!\n\n"
                "Now tell me who to send this invoice to:\n"
                "<code>/invoice &lt;vendor_chat_id&gt;</code>\n\n"
                "Or reply with the vendor's Telegram chat ID:"
            )
            user_state[chat_id] = {
                "action": "awaiting_receiver",
                "image_bytes": image_bytes,
                "mime_type": mime_type,
            }
            return

        receiver = db.query(Merchant).filter(Merchant.id == receiver_id).first()
        if not receiver:
            await update.message.reply_text("❌ Receiver not found.")
            return

        inv = await invoice_service.create_invoice_from_image(
            db=db,
            sender_merchant_id=sender.id,
            receiver_merchant_id=receiver.id,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )

        result = await payment_service.generate_payment_link(db, inv.id)
        payment_link = result.get("payment_link", "")

        await update.message.reply_html(
            f"✅ <b>Invoice Processed!</b>\n\n"
            f"📄 <b>Invoice #:</b> {inv.invoice_number}\n"
            f"💵 <b>Amount:</b> ₹{inv.amount:,.2f}\n"
            f"🔗 <a href=\"{payment_link}\">Payment Link</a>\n\n"
            f"Notification sent to {receiver.business_name}."
        )

        await webhook_service.send_payment_request_notification(
            receiver_chat_id=receiver.telegram_chat_id,
            sender_business_name=sender.business_name,
            invoice_number=inv.invoice_number,
            amount=inv.amount,
            payment_link=payment_link,
        )
    finally:
        db.close()


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text replies (e.g., providing vendor chat ID after image upload)."""
    chat_id = str(update.effective_chat.id)
    state = user_state.get(chat_id, {})

    if state.get("action") == "awaiting_receiver":
        receiver_chat_id = update.message.text.strip()
        db = get_db()
        try:
            receiver = db.query(Merchant).filter_by(telegram_chat_id=receiver_chat_id).first()
            if not receiver:
                await update.message.reply_html(
                    f"❌ No business registered with chat ID <code>{receiver_chat_id}</code>.\n"
                    f"Ask them to /start the bot first."
                )
                return

            sender = get_or_create_merchant(db, chat_id)
            image_bytes = state.get("image_bytes")
            mime_type = state.get("mime_type", "image/jpeg")

            await update.message.reply_text("⚙️ Creating invoice and payment link...")

            inv = await invoice_service.create_invoice_from_image(
                db=db,
                sender_merchant_id=sender.id,
                receiver_merchant_id=receiver.id,
                image_bytes=image_bytes,
                mime_type=mime_type,
            )

            result = await payment_service.generate_payment_link(db, inv.id)
            payment_link = result.get("payment_link", "")

            await update.message.reply_html(
                f"✅ <b>Invoice Created!</b>\n\n"
                f"📄 <b>Invoice #:</b> {inv.invoice_number}\n"
                f"💵 <b>Amount:</b> ₹{inv.amount:,.2f}\n"
                f"🔗 <a href=\"{payment_link}\">Payment Link</a>\n\n"
                f"Notification sent to {receiver.business_name}."
            )

            await webhook_service.send_payment_request_notification(
                receiver_chat_id=receiver_chat_id,
                sender_business_name=sender.business_name,
                invoice_number=inv.invoice_number,
                amount=inv.amount,
                payment_link=payment_link,
            )
            user_state.pop(chat_id, None)
        finally:
            db.close()
    else:
        await update.message.reply_html(
            "💬 Use these commands:\n"
            "/invoice — Create invoice\n"
            "/pending — View pending payments\n"
            "/refund — Issue refund\n"
            "/balance — Balance summary"
        )


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    db = get_db()
    try:
        merchant = get_or_create_merchant(db, chat_id)
        invoices = invoice_service.get_pending_invoices_for_merchant(db, merchant.id)

        if not invoices:
            await update.message.reply_html(
                "✅ <b>No pending payments!</b>\n\n"
                "You have no outstanding invoices to pay."
            )
            return

        text = f"📋 <b>Pending Payments ({len(invoices)})</b>\n\n"
        keyboard = []

        for inv in invoices[:10]:
            sender_name = inv.sender.business_name if inv.sender else "Unknown"
            text += (
                f"📄 <b>{inv.invoice_number}</b>\n"
                f"   From: {sender_name}\n"
                f"   Amount: ₹{inv.amount:,.2f}\n"
                f"   Date: {inv.created_at.strftime('%d %b %Y')}\n\n"
            )
            if inv.payment_link:
                keyboard.append([InlineKeyboardButton(
                    f"💳 Pay {inv.invoice_number} (₹{inv.amount:,.0f})",
                    url=inv.payment_link
                )])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        await update.message.reply_html(text, reply_markup=reply_markup)
    finally:
        db.close()


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    db = get_db()
    try:
        merchant = get_or_create_merchant(db, chat_id)
        summary = invoice_service.get_balance_summary(db, merchant.id)

        net = summary["net"]
        net_emoji = "📈" if net >= 0 else "📉"

        text = (
            f"📊 <b>Balance Summary — {merchant.business_name}</b>\n\n"
            f"💚 <b>Receivable:</b> ₹{summary['total_receivable']:,.2f} ({summary['receivable_count']} invoices)\n"
            f"🔴 <b>Payable:</b> ₹{summary['total_payable']:,.2f} ({summary['payable_count']} invoices)\n"
            f"{'─' * 30}\n"
            f"{net_emoji} <b>Net Position:</b> ₹{abs(net):,.2f} {'in your favor' if net >= 0 else 'owed by you'}\n\n"
            f"Use /pending to view & pay invoices."
        )
        await update.message.reply_html(text)
    finally:
        db.close()


async def cmd_refund(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    args = context.args
    db = get_db()

    try:
        merchant = get_or_create_merchant(db, chat_id)

        if not args:
            paid_invoices = (
                db.query(Invoice)
                .filter(
                    Invoice.sender_merchant_id == merchant.id,
                    Invoice.status == InvoiceStatus.PAID,
                )
                .order_by(Invoice.created_at.desc())
                .limit(10)
                .all()
            )

            if not paid_invoices:
                await update.message.reply_html("❌ No paid invoices eligible for refund.")
                return

            text = "🔄 <b>Eligible Refunds</b>\n\nUse: <code>/refund &lt;invoice_id&gt; [reason]</code>\n\n"
            for inv in paid_invoices:
                receiver_name = inv.receiver.business_name if inv.receiver else "Unknown"
                text += (
                    f"ID: <code>{inv.id}</code> | {inv.invoice_number}\n"
                    f"   To: {receiver_name} | ₹{inv.amount:,.2f}\n"
                    f"   Paid: {inv.paid_at.strftime('%d %b %Y') if inv.paid_at else 'N/A'}\n\n"
                )
            await update.message.reply_html(text)
            return

        invoice_id = int(args[0])
        reason = " ".join(args[1:]) if len(args) > 1 else "Refund requested"

        inv = invoice_service.get_invoice_by_id(db, invoice_id)
        if not inv:
            await update.message.reply_text("❌ Invoice not found.")
            return

        if inv.sender_merchant_id != merchant.id:
            await update.message.reply_text("❌ You can only refund invoices you sent.")
            return

        result = await refund_service.issue_refund(db, invoice_id, reason=reason)

        if result["success"]:
            await update.message.reply_html(
                f"✅ <b>Refund Initiated!</b>\n\n"
                f"📄 Invoice: {result['invoice_number']}\n"
                f"💵 Amount: ₹{result['amount']:,.2f}\n"
                f"📝 Reason: {reason}"
            )

            if inv.receiver:
                await webhook_service.send_refund_notification(
                    sender_chat_id=chat_id,
                    receiver_chat_id=inv.receiver.telegram_chat_id,
                    invoice_number=inv.invoice_number,
                    amount=result["amount"],
                    reason=reason,
                )
        else:
            await update.message.reply_html(f"❌ Refund failed: {result.get('error')}")

    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid invoice ID.")
    finally:
        db.close()


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    await update.message.reply_html(
        f"🆔 Your Telegram Chat ID: <code>{chat_id}</code>\n\n"
        f"Share this with others so they can send you invoices."
    )


def build_application() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("register", cmd_register))
    app.add_handler(CommandHandler("invoice", cmd_invoice))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("refund", cmd_refund))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("myid", cmd_myid))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_document_or_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    return app
