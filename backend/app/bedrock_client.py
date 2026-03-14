import boto3
from botocore.exceptions import ClientError
import base64
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")


def get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN", ""),
    )


async def parse_invoice_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[dict]:
    """
    Use AWS Bedrock Claude to OCR and parse an invoice image.
    Returns structured invoice data including line items, amounts, and parties.
    """
    prompt = """You are an invoice parsing assistant. Analyze this invoice image and extract the following information in JSON format:

{
  "vendor_name": "name of the seller/vendor",
  "customer_name": "name of the buyer/customer",
  "invoice_number": "invoice number if visible",
  "invoice_date": "date of invoice (YYYY-MM-DD format)",
  "due_date": "due date if visible (YYYY-MM-DD format)",
  "line_items": [
    {
      "description": "item description",
      "quantity": 1,
      "unit_price": 100.00,
      "total": 100.00
    }
  ],
  "subtotal": 0.00,
  "tax": 0.00,
  "total_amount": 0.00,
  "currency": "INR",
  "notes": "any additional notes"
}

If any field is not visible or cannot be determined, use null. 
Return ONLY the JSON object, no additional text.
For handwritten invoices, do your best to interpret the text."""

    try:
        client = get_bedrock_client()

        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        media_type = mime_type if mime_type in ["image/jpeg", "image/png", "image/gif", "image/webp"] else "image/jpeg"

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        })

        logger.info(f"Invoking Bedrock model: {BEDROCK_MODEL_ID} in region: {AWS_REGION}")
        
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        raw_body = response["body"].read()
        logger.info(f"Bedrock raw response length: {len(raw_body)} bytes")
        
        if not raw_body:
            logger.error("Bedrock returned empty response body")
            return _fallback_parse(image_bytes)
        
        response_body = json.loads(raw_body)
        
        if "error" in response_body:
            logger.error(f"Bedrock API error: {response_body['error']}")
            return _fallback_parse(image_bytes)
        
        text_response = response_body["content"][0]["text"]
        
        text_response = text_response.strip()
        if text_response.startswith("```json"):
            text_response = text_response[7:]
        if text_response.startswith("```"):
            text_response = text_response[3:]
        if text_response.endswith("```"):
            text_response = text_response[:-3]
        text_response = text_response.strip()

        parsed = json.loads(text_response)
        logger.info(f"Bedrock invoice parsed successfully: {parsed.get('invoice_number')}")
        return parsed

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Bedrock API error [{error_code}]: {error_message}")
        if error_code == "AccessDeniedException":
            logger.error(f"Check IAM permissions for model {BEDROCK_MODEL_ID}")
        elif error_code == "ValidationException":
            logger.error(f"Model ID '{BEDROCK_MODEL_ID}' may be invalid or not enabled in region {AWS_REGION}")
        elif error_code == "ResourceNotFoundException":
            logger.error(f"Model '{BEDROCK_MODEL_ID}' not found in region {AWS_REGION}")
        elif error_code == "ThrottlingException":
            logger.error("Request throttled - consider adding retry logic")
        return _fallback_parse(image_bytes)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude's response as JSON: {e}")
        return _fallback_parse(image_bytes)
    except Exception as e:
        logger.error(f"Bedrock invoice parsing error ({type(e).__name__}): {e}")
        return _fallback_parse(image_bytes)


def _fallback_parse(image_bytes: bytes) -> dict:
    """Fallback structure when Bedrock is unavailable."""
    return {
        "vendor_name": None,
        "customer_name": None,
        "invoice_number": None,
        "invoice_date": None,
        "due_date": None,
        "line_items": [],
        "subtotal": 0.0,
        "tax": 0.0,
        "total_amount": 0.0,
        "currency": "INR",
        "notes": "Invoice parsed manually - OCR unavailable",
        "_parse_error": True,
    }
