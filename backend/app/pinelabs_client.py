import httpx
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PINELABS_BASE_URL = os.getenv("PINELABS_BASE_URL", "https://pluraluat.v2.pinepg.in")
PINELABS_CLIENT_ID = os.getenv("PINELABS_CLIENT_ID", "")
PINELABS_CLIENT_SECRET = os.getenv("PINELABS_CLIENT_SECRET", "")
PINELABS_MERCHANT_ID = os.getenv("PINELABS_MERCHANT_ID", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://nonsentiently-wonderless-elanor.ngrok-free.dev")

_access_token: Optional[str] = None
_token_expiry: Optional[datetime] = None


def _get_headers(include_auth: bool = True) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Request-ID": str(uuid.uuid4()),
        "Request-Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    if include_auth and _access_token:
        headers["Authorization"] = f"Bearer {_access_token}"
    return headers


async def _get_access_token() -> Optional[str]:
    """Get OAuth access token from Plural API."""
    global _access_token, _token_expiry
    
    if _access_token and _token_expiry and datetime.now(timezone.utc) < _token_expiry:
        return _access_token
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{PINELABS_BASE_URL}/api/auth/v1/token"
            payload = {
                "client_id": PINELABS_CLIENT_ID,
                "client_secret": PINELABS_CLIENT_SECRET,
                "grant_type": "client_credentials"
            }
            response = await client.post(url, json=payload, headers=_get_headers(include_auth=False))
            response.raise_for_status()
            data = response.json()
            _access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            _token_expiry = datetime.now(timezone.utc).replace(microsecond=0)
            from datetime import timedelta
            _token_expiry += timedelta(seconds=expires_in - 60)
            logger.info("Plural access token obtained successfully")
            return _access_token
    except httpx.HTTPStatusError as e:
        logger.error(f"Plural auth error: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Plural auth connection error: {e}")
        return None


async def create_payment_link(
    merchant_order_reference: str,
    amount_paise: int,
    customer_name: str,
    customer_email: Optional[str] = None,
    customer_mobile: Optional[str] = None,
    description: str = "Invoice Payment",
) -> dict:
    """Create a Plural payment link for a given invoice."""
    token = await _get_access_token()
    if not token:
        logger.warning("Could not obtain Plural access token, using fallback")
        return {"success": False, "error": "Authentication failed", "fallback_url": f"{APP_BASE_URL}/demo/pay/{merchant_order_reference}"}
    
    truncated_description = description[:100] if len(description) > 100 else description
    
    payload = {
        "merchant_payment_link_reference": merchant_order_reference,
        "amount": {
            "value": amount_paise,
            "currency": "INR"
        },
        "description": truncated_description,
        "customer": {
            "first_name": customer_name.split()[0] if customer_name else "Customer",
            "last_name": " ".join(customer_name.split()[1:]) if customer_name and len(customer_name.split()) > 1 else "",
        },
        "callback_url": f"{APP_BASE_URL}/payment/webhook",
    }
    
    if customer_email:
        payload["customer"]["email"] = customer_email
    if customer_mobile:
        payload["customer"]["mobile_number"] = customer_mobile

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{PINELABS_BASE_URL}/api/pay/v1/paymentlink"
            response = await client.post(url, json=payload, headers=_get_headers())
            response.raise_for_status()
            data = response.json()
            logger.info(f"Plural payment link created: {data}")
            return {"success": True, "data": data}
    except httpx.HTTPStatusError as e:
        logger.error(f"Plural API error: {e.response.status_code} - {e.response.text}")
        return {"success": False, "error": str(e), "fallback_url": f"{APP_BASE_URL}/demo/pay/{merchant_order_reference}"}
    except Exception as e:
        logger.error(f"Plural connection error: {e}")
        return {"success": False, "error": str(e), "fallback_url": f"{APP_BASE_URL}/demo/pay/{merchant_order_reference}"}


async def create_order(
    merchant_order_reference: str,
    amount_paise: int,
    customer_name: str,
    customer_email: Optional[str] = None,
    customer_mobile: Optional[str] = None,
    description: str = "Invoice Payment",
) -> dict:
    """Create a Plural checkout order."""
    token = await _get_access_token()
    if not token:
        logger.warning("Could not obtain Plural access token, using fallback")
        return {"success": False, "error": "Authentication failed", "fallback_url": f"{APP_BASE_URL}/demo/pay/{merchant_order_reference}"}
    
    payload = {
        "merchant_order_reference": merchant_order_reference,
        "amount": {
            "value": amount_paise,
            "currency": "INR"
        },
        "customer": {
            "first_name": customer_name.split()[0] if customer_name else "Customer",
            "last_name": " ".join(customer_name.split()[1:]) if customer_name and len(customer_name.split()) > 1 else "",
        },
        "callback_url": f"{APP_BASE_URL}/payment/webhook",
        "notes": description,
    }
    
    if customer_email:
        payload["customer"]["email"] = customer_email
    if customer_mobile:
        payload["customer"]["mobile_number"] = customer_mobile

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{PINELABS_BASE_URL}/api/pay/v1/orders"
            response = await client.post(url, json=payload, headers=_get_headers())
            response.raise_for_status()
            data = response.json()
            logger.info(f"Plural order created: {data}")
            return {"success": True, "data": data}
    except httpx.HTTPStatusError as e:
        logger.error(f"Plural order API error: {e.response.status_code} - {e.response.text}")
        return {"success": False, "error": str(e), "fallback_url": f"{APP_BASE_URL}/demo/pay/{merchant_order_reference}"}
    except Exception as e:
        logger.error(f"Plural order connection error: {e}")
        return {"success": False, "error": str(e), "fallback_url": f"{APP_BASE_URL}/demo/pay/{merchant_order_reference}"}


async def get_order(order_id: str) -> dict:
    """Fetch order details by Plural order ID."""
    token = await _get_access_token()
    if not token:
        return {"success": False, "error": "Authentication failed"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{PINELABS_BASE_URL}/api/pay/v1/orders/{order_id}"
            response = await client.get(url, headers=_get_headers())
            response.raise_for_status()
            return {"success": True, "data": response.json()}
    except Exception as e:
        logger.error(f"Plural get order error: {e}")
        return {"success": False, "error": str(e)}


async def get_payment_link(payment_link_id: str) -> dict:
    """Fetch payment link details."""
    token = await _get_access_token()
    if not token:
        return {"success": False, "error": "Authentication failed"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{PINELABS_BASE_URL}/api/pay/v1/paymentlink/{payment_link_id}"
            response = await client.get(url, headers=_get_headers())
            response.raise_for_status()
            return {"success": True, "data": response.json()}
    except Exception as e:
        logger.error(f"Plural get payment link error: {e}")
        return {"success": False, "error": str(e)}


async def initiate_refund(
    order_id: str,
    merchant_order_reference: str,
    amount_paise: int,
    reason: str = "Refund requested",
) -> dict:
    """Initiate a refund for a Plural order."""
    token = await _get_access_token()
    if not token:
        return {"success": False, "error": "Authentication failed"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{PINELABS_BASE_URL}/api/pay/v1/orders/{order_id}/refund"
            payload = {
                "merchant_refund_reference": f"REFUND_{merchant_order_reference}_{uuid.uuid4().hex[:8]}",
                "amount": {
                    "value": amount_paise,
                    "currency": "INR"
                },
            }
            response = await client.post(url, json=payload, headers=_get_headers())
            response.raise_for_status()
            data = response.json()
            logger.info(f"Plural refund initiated: {data}")
            return {"success": True, "data": data}
    except httpx.HTTPStatusError as e:
        logger.error(f"Plural refund API error: {e.response.status_code} - {e.response.text}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Plural refund error: {e}")
        return {"success": False, "error": str(e)}


async def resend_payment_link_notification(payment_link_id: str) -> dict:
    """Resend payment link notification to customer."""
    token = await _get_access_token()
    if not token:
        return {"success": False, "error": "Authentication failed"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{PINELABS_BASE_URL}/api/pay/v1/paymentlink/{payment_link_id}/resend"
            response = await client.post(url, headers=_get_headers())
            response.raise_for_status()
            return {"success": True, "data": response.json()}
    except Exception as e:
        logger.error(f"Plural resend notification error: {e}")
        return {"success": False, "error": str(e)}
