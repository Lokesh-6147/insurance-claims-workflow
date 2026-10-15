import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.event_retry_publisher import (
    publish_dead_letter,
    publish_retry_message,
)
from services.event_retry_policy import DEAD_LETTER_QUEUE, RETRY_QUEUE


def test_retry_message_has_incremented_count_and_is_persistent():
    channel = MagicMock()
    properties = SimpleNamespace(
        headers={"source": "test"},
        content_type="application/json",
    )
    message = {
        "event_id": 7,
        "event_type": "CLAIM_SUBMITTED",
        "claim": {"claim_id": 12},
    }

    publish_retry_message(channel, message, properties, 1)

    kwargs = channel.basic_publish.call_args.kwargs
    assert kwargs["exchange"] == ""
    assert kwargs["routing_key"] == RETRY_QUEUE
    assert kwargs["mandatory"] is True
    assert json.loads(kwargs["body"]) == message
    assert kwargs["properties"].delivery_mode == 2
    assert kwargs["properties"].headers == {
        "source": "test",
        "x-retry-count": 1,
    }


def test_dead_letter_keeps_original_body_and_reason():
    channel = MagicMock()
    properties = SimpleNamespace(
        headers={"x-retry-count": 3},
        content_type="application/json",
    )
    body = b'{"event_id":7,"event_type":"CLAIM_SUBMITTED"}'

    publish_dead_letter(
        channel, body, properties, "processing failed", retry_count=3
    )

    kwargs = channel.basic_publish.call_args.kwargs
    assert kwargs["exchange"] == ""
    assert kwargs["routing_key"] == DEAD_LETTER_QUEUE
    assert kwargs["body"] == body
    assert kwargs["mandatory"] is True
    assert kwargs["properties"].delivery_mode == 2
    assert kwargs["properties"].headers["x-retry-count"] == 3
    assert kwargs["properties"].headers["x-dead-letter-reason"] == (
        "processing failed"
    )


def test_dead_letter_without_content_type_uses_json():
    channel = MagicMock()
    properties = SimpleNamespace(headers=None, content_type=None)

    publish_dead_letter(channel, b"bad message", properties, "invalid JSON")

    kwargs = channel.basic_publish.call_args.kwargs
    assert kwargs["properties"].content_type == "application/json"

def test_dead_letter_truncates_long_reason():
    channel = MagicMock()
    properties = SimpleNamespace(headers=None, content_type=None)
    long_reason = "x" * 700

    publish_dead_letter(
        channel,
        b"bad message",
        properties,
        long_reason,
    )

    kwargs = channel.basic_publish.call_args.kwargs
    reason = kwargs["properties"].headers["x-dead-letter-reason"]

    assert len(reason) == 500
    assert reason == "x" * 500
