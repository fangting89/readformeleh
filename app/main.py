"""FastAPI app and Twilio WhatsApp webhook route."""

import hashlib
import logging
import tempfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request, Response
from twilio.twiml.messaging_response import MessagingResponse

from app import messages
from app.state import (
    ConsecutiveFailureCount,
    LanguageCache,
    LanguagePreference,
    RateLimiter,
    SeenMessages,
)
from app.twilio_client import download_media, send_message, verify_signature
from pipeline.classify import classify_letter
from pipeline.summarize import summarize_letter_checked, translate_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("read_leh")

app = FastAPI()

_language_cache = LanguageCache()
_language_preference = LanguagePreference()
_rate_limiter = RateLimiter()
_seen_messages = SeenMessages()
_consecutive_failures = ConsecutiveFailureCount()

# Consecutive unreadable/degraded results from the same sender before the
# retry message escalates to suggesting in-person help (see
# docs/DESIGN.md's evidence base on staff time/stigma).
_ESCALATION_THRESHOLD = 2


def _hash_sender(sender: str) -> str:
    """Short, non-reversible sender identifier for logs — the phone
    number itself is PII and is never logged raw."""
    return hashlib.sha256(sender.encode()).hexdigest()[:12]


def _twiml(body: str) -> Response:
    response = MessagingResponse()
    response.message(body)
    return Response(content=str(response), media_type="application/xml")


def _unreadable_reply(sender: str) -> str:
    """Records a failed (unreadable or degraded) attempt for the sender and
    returns the appropriate retry message — the baseline tip on the first
    failure, or the escalated in-person-help suggestion once
    _ESCALATION_THRESHOLD consecutive failures have piled up."""
    count = _consecutive_failures.record_failure(sender)
    if count >= _ESCALATION_THRESHOLD:
        return messages.UNREADABLE_RETRY_ESCALATED
    return messages.UNREADABLE_RETRY


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def whatsapp_webhook(
    request: Request, background_tasks: BackgroundTasks
) -> Response:
    """Twilio WhatsApp webhook: receives a letter photo, replies with a summary."""
    form = await request.form()
    params = dict(form)
    signature = request.headers.get("X-Twilio-Signature", "")

    if not verify_signature(str(request.url), params, signature):
        logger.warning("rejected webhook request: invalid signature")
        return Response(status_code=403)

    message_sid = params.get("MessageSid", "")
    sender = params.get("From", "")
    body = params.get("Body", "").strip()
    num_media = params.get("NumMedia", "0")
    media_url = params.get("MediaUrl0")
    sender_hash = _hash_sender(sender)

    if _seen_messages.seen_before(message_sid):
        logger.info("duplicate webhook delivery for sender=%s, ignoring", sender_hash)
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    if not _rate_limiter.allow(sender):
        logger.info("rate limited sender=%s", sender_hash)
        return _twiml(messages.RATE_LIMITED)

    if num_media != "0" and media_url:
        logger.info("received letter photo from sender=%s", sender_hash)
        background_tasks.add_task(_process_letter, sender, media_url, sender_hash)
        return _twiml(messages.ACK)

    lowered_body = body.lower()
    if (
        lowered_body in messages.CHINESE_KEYWORDS
        or lowered_body in messages.ENGLISH_KEYWORDS
    ):
        target_lang = "zh" if lowered_body in messages.CHINESE_KEYWORDS else "en"
        _language_preference.set(sender, target_lang)
        logger.info("sender=%s set language preference=%s", sender_hash, target_lang)

        cached_en = _language_cache.get(sender)
        if cached_en is None:
            return _twiml(messages.NO_CACHED_SUMMARY)
        if target_lang == "en":
            return _twiml(cached_en)
        return _twiml(translate_summary(cached_en, "zh"))

    return _twiml(messages.USAGE_INSTRUCTIONS)


def _process_letter(sender: str, media_url: str, sender_hash: str) -> None:
    """Runs off the request/response cycle via FastAPI's BackgroundTasks.

    Defined as a plain (non-async) function so Starlette runs it in a
    worker thread automatically, rather than blocking the event loop for
    the several seconds a classify+summarize round trip takes.
    """
    try:
        image_bytes = download_media(media_url)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
            tmp.write(image_bytes)
            tmp.flush()
            image_path = Path(tmp.name)

            result = classify_letter(image_path)
            logger.info(
                "classified sender=%s category=%s", sender_hash, result["category"]
            )

            if result["category"] == "suspicious":
                # Safe to log: classify_letter's prompt requires red flags to
                # be described generically, never quoting NRIC/address/amount
                # from the letter itself.
                logger.info(
                    "sender=%s flagged suspicious, red_flags=%s",
                    sender_hash,
                    result["red_flags"],
                )
                _consecutive_failures.reset(sender)  # photo was legible
                send_message(sender, messages.SUSPICIOUS_WARNING)
                return
            if result["category"] == "unreadable":
                send_message(sender, _unreadable_reply(sender))
                return
            if result["image_quality"] == "degraded":
                # Category was determinable but specific figures weren't.
                # a stricter bar than "unreadable". Route to the same
                # retry message rather than risk summarize_letter guessing
                # at an amount or date it can't actually read (see
                # docs/DESIGN.md Design Decision 3 for what this caught).
                logger.info(
                    "sender=%s category=%s but image_quality=degraded, skipping summarize",
                    sender_hash,
                    result["category"],
                )
                send_message(sender, _unreadable_reply(sender))
                return

            # Always generate the English summary as the base — it's the
            # letter's original language, so a direct extraction is more
            # faithful than translating a translation. Cache it so later
            # toggles/preferences can re-render from a consistent source.
            # image_quality is "clear" here (the "degraded" branch above
            # already returned), so summarize_letter_checked's extra
            # independent read is warranted — see its docstring and
            # docs/DESIGN.md for the hallucination case it catches.
            summary_en = summarize_letter_checked(image_path)
            _language_cache.set(sender, summary_en)
            _consecutive_failures.reset(sender)

            preference = _language_preference.get(sender)
            if preference == "en":
                reply = summary_en
            elif preference == "zh":
                reply = translate_summary(summary_en, "zh")
            else:
                # No preference known yet — bilingual by default, since a
                # sender who can't read English may not understand an
                # English-only instruction telling them how to ask for
                # Mandarin.
                reply = messages.bilingual_summary(
                    summary_en, translate_summary(summary_en, "zh")
                )

            send_message(sender, reply)
            logger.info("replied sender=%s (preference=%s)", sender_hash, preference)
    except Exception:
        logger.exception("error processing letter for sender=%s", sender_hash)
        send_message(sender, messages.PROCESSING_ERROR)
