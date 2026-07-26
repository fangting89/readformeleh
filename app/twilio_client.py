"""Twilio-specific I/O: webhook signature verification, media download,
and outbound messages."""

import requests
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from pipeline.config import require_env


def verify_signature(url: str, params: dict[str, str], signature: str) -> bool:
    """Verifies a Twilio webhook request actually came from Twilio.

    `url` must be the exact public URL Twilio called (the https ngrok URL
    configured in the console). If running behind a proxy that rewrites
    scheme/host, reconstruct the original URL rather than using what
    uvicorn sees locally, or the signature will never match.

    Args:
        url: The webhook URL as Twilio would have seen it.
        params: The POST form parameters, as received.
        signature: The `X-Twilio-Signature` header value.

    Returns:
        True if the request is authentically from Twilio.
    """
    validator = RequestValidator(require_env("TWILIO_AUTH_TOKEN"))
    return validator.validate(url, params, signature)


def download_media(media_url: str) -> bytes:
    """Downloads inbound WhatsApp media from Twilio.

    Args:
        media_url: The `MediaUrl0` value from the webhook payload.

    Returns:
        The raw image bytes.
    """
    account_sid = require_env("TWILIO_ACCOUNT_SID")
    auth_token = require_env("TWILIO_AUTH_TOKEN")
    response = requests.get(media_url, auth=(account_sid, auth_token), timeout=30)
    response.raise_for_status()
    return response.content


def send_message(to: str, body: str) -> None:
    """Sends a WhatsApp message via the Twilio REST API.

    Used for the async follow-up after the immediate TwiML ack, since
    pipeline processing takes longer than a webhook response should.

    Args:
        to: Recipient, in Twilio's `whatsapp:+<number>` form (the `From`
            value of the inbound webhook can be reused directly).
        body: Message text.
    """
    account_sid = require_env("TWILIO_ACCOUNT_SID")
    auth_token = require_env("TWILIO_AUTH_TOKEN")
    from_number = require_env("TWILIO_WHATSAPP_NUMBER")
    client = Client(account_sid, auth_token)
    client.messages.create(from_=from_number, to=to, body=body)
