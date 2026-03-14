import httpx
import logging
import os

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_telegram_message(chat_id: str | int, text: str, parse_mode: str = "HTML") -> bool:
    """Send a message to a Telegram chat."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping notification")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False,
            }
            logger.debug(f"Sending Telegram message to {chat_id}: {text[:100]}...")
            response = await client.post(
                f"{TELEGRAM_API_BASE}/sendMessage",
                json=payload,
            )
            response_data = response.json()
            if response.status_code == 200 and response_data.get("ok"):
                logger.info(f"Telegram message sent to {chat_id}")
                return True
            logger.error(f"Telegram send error: {response.status_code} - {response_data}")
            return False
    except Exception as e:
        logger.error(f"Telegram notification error: {e}")
        return False


async def send_payment_request_notification(
    receiver_chat_id: str,
    sender_business_name: str,
    invoice_number: str,
    amount: float,
    payment_link: str,
) -> bool:
    text = (
        f"💰 <b>Payment Request</b>\n\n"
        f"<b>{sender_business_name}</b> has sent you an invoice.\n\n"
        f"📄 Invoice: <code>{invoice_number}</code>\n"
        f"💵 Amount: <b>₹{amount:,.2f}</b>\n\n"
        f"<a href=\"{payment_link}\">👆 Pay Now</a>\n\n"
        f"Use /pending to view all pending payments."
    )
    return await send_telegram_message(receiver_chat_id, text)


async def send_payment_confirmation(
    sender_chat_id: str,
    receiver_chat_id: str,
    sender_business_name: str,
    receiver_business_name: str,
    invoice_number: str,
    amount: float,
) -> None:
    sender_text = (
        f"✅ <b>Payment Received!</b>\n\n"
        f"<b>{receiver_business_name}</b> has paid your invoice.\n\n"
        f"📄 Invoice: <code>{invoice_number}</code>\n"
        f"💵 Amount: <b>₹{amount:,.2f}</b>"
    )
    receiver_text = (
        f"✅ <b>Payment Successful!</b>\n\n"
        f"Your payment to <b>{sender_business_name}</b> was successful.\n\n"
        f"📄 Invoice: <code>{invoice_number}</code>\n"
        f"💵 Amount: <b>₹{amount:,.2f}</b>"
    )
    await send_telegram_message(sender_chat_id, sender_text)
    await send_telegram_message(receiver_chat_id, receiver_text)


async def send_refund_notification(
    sender_chat_id: str,
    receiver_chat_id: str,
    invoice_number: str,
    amount: float,
    reason: str = "",
) -> None:
    text = (
        f"🔄 <b>Refund Initiated</b>\n\n"
        f"📄 Invoice: <code>{invoice_number}</code>\n"
        f"💵 Refund Amount: <b>₹{amount:,.2f}</b>\n"
        f"📝 Reason: {reason or 'Not specified'}"
    )
    await send_telegram_message(sender_chat_id, text)
    await send_telegram_message(receiver_chat_id, text)
