"""Tests for the app/main.py webhook route."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app import messages
from app.main import _language_cache, _language_preference, app

client = TestClient(app)


def _webhook_payload(**overrides):
    payload = {
        "MessageSid": "SM_default",
        "From": "whatsapp:+10000000000",
        "Body": "",
        "NumMedia": "0",
    }
    payload.update(overrides)
    return payload


@patch("app.main.verify_signature", return_value=False)
def test_webhook_rejects_invalid_signature(mock_verify):
    response = client.post("/webhook", data=_webhook_payload(MessageSid="SM1"))
    assert response.status_code == 403


@patch("app.main.verify_signature", return_value=True)
def test_webhook_no_media_returns_usage_instructions(mock_verify):
    response = client.post(
        "/webhook",
        data=_webhook_payload(MessageSid="SM2", From="whatsapp:+10000000002"),
    )
    assert response.status_code == 200
    assert "photo" in response.text.lower()
    assert "信件" in response.text  # bilingual: Chinese half present too


@patch("app.main.translate_summary", return_value="中文摘要")
@patch("app.main.send_message")
@patch("app.main.summarize_letter_checked", return_value="an english summary")
@patch(
    "app.main.classify_letter",
    return_value={"category": "government", "image_quality": "clear", "red_flags": []},
)
@patch("app.main.download_media", return_value=b"fake-image-bytes")
@patch("app.main.verify_signature", return_value=True)
def test_webhook_first_contact_sends_bilingual_summary(
    mock_verify, mock_download, mock_classify, mock_summarize, mock_send, mock_translate
):
    sender = "whatsapp:+10000000003"
    response = client.post(
        "/webhook",
        data=_webhook_payload(
            MessageSid="SM3",
            From=sender,
            NumMedia="1",
            MediaUrl0="https://example.com/media/1",
        ),
    )
    assert response.status_code == 200
    assert "moment" in response.text.lower()  # the ack, in the immediate TwiML reply
    mock_translate.assert_called_once_with("an english summary", "zh")
    sent_body = mock_send.call_args[0][1]
    assert "an english summary" in sent_body
    assert "中文摘要" in sent_body
    assert _language_cache.get(sender) == "an english summary"


@patch("app.main.translate_summary")
@patch("app.main.send_message")
@patch("app.main.summarize_letter_checked", return_value="an english summary")
@patch(
    "app.main.classify_letter",
    return_value={"category": "government", "image_quality": "clear", "red_flags": []},
)
@patch("app.main.download_media", return_value=b"fake-image-bytes")
@patch("app.main.verify_signature", return_value=True)
def test_webhook_with_media_sends_english_only_when_preference_is_english(
    mock_verify, mock_download, mock_classify, mock_summarize, mock_send, mock_translate
):
    sender = "whatsapp:+10000000010"
    _language_preference.set(sender, "en")
    client.post(
        "/webhook",
        data=_webhook_payload(
            MessageSid="SM10",
            From=sender,
            NumMedia="1",
            MediaUrl0="https://example.com/media/x",
        ),
    )
    mock_translate.assert_not_called()
    assert mock_send.call_args[0][1] == "an english summary"


@patch("app.main.translate_summary", return_value="中文摘要")
@patch("app.main.send_message")
@patch("app.main.summarize_letter_checked", return_value="an english summary")
@patch(
    "app.main.classify_letter",
    return_value={"category": "government", "image_quality": "clear", "red_flags": []},
)
@patch("app.main.download_media", return_value=b"fake-image-bytes")
@patch("app.main.verify_signature", return_value=True)
def test_webhook_with_media_sends_chinese_only_when_preference_is_chinese(
    mock_verify, mock_download, mock_classify, mock_summarize, mock_send, mock_translate
):
    sender = "whatsapp:+10000000011"
    _language_preference.set(sender, "zh")
    client.post(
        "/webhook",
        data=_webhook_payload(
            MessageSid="SM11",
            From=sender,
            NumMedia="1",
            MediaUrl0="https://example.com/media/y",
        ),
    )
    assert mock_send.call_args[0][1] == "中文摘要"


@patch("app.main.send_message")
@patch("app.main.summarize_letter_checked")
@patch(
    "app.main.classify_letter",
    return_value={
        "category": "suspicious",
        "scam_type": "impersonation",
        "red_flags": ["urgent threat"],
    },
)
@patch("app.main.download_media", return_value=b"fake-image-bytes")
@patch("app.main.verify_signature", return_value=True)
def test_webhook_suspicious_letter_skips_summary(
    mock_verify, mock_download, mock_classify, mock_summarize, mock_send
):
    sender = "whatsapp:+10000000004"
    client.post(
        "/webhook",
        data=_webhook_payload(
            MessageSid="SM4",
            From=sender,
            NumMedia="1",
            MediaUrl0="https://example.com/media/2",
        ),
    )
    mock_summarize.assert_not_called()
    assert mock_send.call_args[0][0] == sender
    assert "suspicious" in mock_send.call_args[0][1].lower()


@patch("app.main.send_message")
@patch(
    "app.main.classify_letter", return_value={"category": "unreadable", "red_flags": []}
)
@patch("app.main.download_media", return_value=b"fake-image-bytes")
@patch("app.main.verify_signature", return_value=True)
def test_webhook_unreadable_letter_asks_for_retry(
    mock_verify, mock_download, mock_classify, mock_send
):
    """A single, first-time unreadable result gets the baseline retry tip,
    not the escalated in-person-help message (see the escalation tests
    below for the second-in-a-row case)."""
    sender = "whatsapp:+10000000005"
    client.post(
        "/webhook",
        data=_webhook_payload(
            MessageSid="SM5",
            From=sender,
            NumMedia="1",
            MediaUrl0="https://example.com/media/3",
        ),
    )
    assert mock_send.call_args[0][0] == sender
    assert mock_send.call_args[0][1] == messages.UNREADABLE_RETRY


@patch("app.main.send_message")
@patch("app.main.summarize_letter_checked")
@patch(
    "app.main.classify_letter",
    return_value={
        "category": "government",
        "image_quality": "degraded",
        "red_flags": [],
    },
)
@patch("app.main.download_media", return_value=b"fake-image-bytes")
@patch("app.main.verify_signature", return_value=True)
def test_webhook_degraded_quality_skips_summary_even_with_known_category(
    mock_verify, mock_download, mock_classify, mock_summarize, mock_send
):
    """A category can be determinable (government) while the photo is
    still too degraded to safely extract specific figures from. This
    must skip summarize_letter just like an outright unreadable photo,
    not just a suspicious one (see docs/DESIGN.md Design Decision 3)."""
    sender = "whatsapp:+10000000013"
    client.post(
        "/webhook",
        data=_webhook_payload(
            MessageSid="SM13",
            From=sender,
            NumMedia="1",
            MediaUrl0="https://example.com/media/4",
        ),
    )
    mock_summarize.assert_not_called()
    assert mock_send.call_args[0][0] == sender
    assert "clearly" in mock_send.call_args[0][1].lower()


@patch("app.main.translate_summary", return_value="翻译后的摘要")
@patch("app.main.verify_signature", return_value=True)
def test_webhook_chinese_keyword_sets_preference_and_translates_cached_summary(
    mock_verify, mock_translate
):
    sender = "whatsapp:+10000000006"
    _language_cache.set(sender, "an english summary")
    response = client.post(
        "/webhook", data=_webhook_payload(MessageSid="SM6", From=sender, Body="中文")
    )
    assert response.status_code == 200
    mock_translate.assert_called_once_with("an english summary", "zh")
    assert "翻译" in response.text
    assert _language_preference.get(sender) == "zh"


@patch("app.main.translate_summary")
@patch("app.main.verify_signature", return_value=True)
def test_webhook_english_keyword_sets_preference_and_returns_cached_summary_directly(
    mock_verify, mock_translate
):
    sender = "whatsapp:+10000000012"
    _language_cache.set(sender, "an english summary")
    response = client.post(
        "/webhook",
        data=_webhook_payload(MessageSid="SM12", From=sender, Body="English"),
    )
    assert response.status_code == 200
    mock_translate.assert_not_called()
    assert "an english summary" in response.text
    assert _language_preference.get(sender) == "en"


@patch("app.main.verify_signature", return_value=True)
def test_webhook_language_keyword_without_cache(mock_verify):
    response = client.post(
        "/webhook",
        data=_webhook_payload(
            MessageSid="SM7", From="whatsapp:+10000000007", Body="中文"
        ),
    )
    assert response.status_code == 200
    assert "again" in response.text.lower()


@patch("app.main.verify_signature", return_value=True)
def test_webhook_rate_limits_after_max_requests(mock_verify):
    sender = "whatsapp:+10000000099"
    for i in range(5):
        response = client.post(
            "/webhook", data=_webhook_payload(MessageSid=f"SM_rl_{i}", From=sender)
        )
        assert response.status_code == 200

    response = client.post(
        "/webhook", data=_webhook_payload(MessageSid="SM_rl_5", From=sender)
    )
    assert "wait" in response.text.lower()


@patch("app.main.verify_signature", return_value=True)
def test_webhook_ignores_duplicate_message_sid(mock_verify):
    payload = _webhook_payload(MessageSid="SM_dup", From="whatsapp:+10000000008")
    first = client.post("/webhook", data=payload)
    second = client.post("/webhook", data=payload)
    assert first.status_code == 200
    assert second.status_code == 200


@patch("app.main.send_message")
@patch(
    "app.main.classify_letter", return_value={"category": "unreadable", "red_flags": []}
)
@patch("app.main.download_media", return_value=b"fake-image-bytes")
@patch("app.main.verify_signature", return_value=True)
def test_webhook_second_consecutive_unreadable_escalates_retry_message(
    mock_verify, mock_download, mock_classify, mock_send
):
    sender = "whatsapp:+10000000014"
    for i in range(2):
        client.post(
            "/webhook",
            data=_webhook_payload(
                MessageSid=f"SM14_{i}",
                From=sender,
                NumMedia="1",
                MediaUrl0="https://example.com/media/5",
            ),
        )
    assert mock_send.call_args[0][1] == messages.UNREADABLE_RETRY_ESCALATED


@patch("app.main.send_message")
@patch("app.main.summarize_letter_checked", return_value="an english summary")
@patch(
    "app.main.classify_letter",
    return_value={"category": "government", "image_quality": "clear", "red_flags": []},
)
@patch("app.main.download_media", return_value=b"fake-image-bytes")
@patch("app.main.verify_signature", return_value=True)
def test_webhook_successful_summary_resets_failure_streak(
    mock_verify, mock_download, mock_classify, mock_summarize, mock_send
):
    """A legible photo after prior failures shouldn't carry an escalated
    tone into a later, unrelated failure streak."""
    sender = "whatsapp:+10000000016"
    client.post(
        "/webhook",
        data=_webhook_payload(
            MessageSid="SM16_success",
            From=sender,
            NumMedia="1",
            MediaUrl0="https://example.com/media/7",
        ),
    )
    mock_classify.return_value = {
        "category": "unreadable",
        "red_flags": [],
    }
    client.post(
        "/webhook",
        data=_webhook_payload(
            MessageSid="SM16_fail",
            From=sender,
            NumMedia="1",
            MediaUrl0="https://example.com/media/8",
        ),
    )
    assert mock_send.call_args[0][1] == messages.UNREADABLE_RETRY
