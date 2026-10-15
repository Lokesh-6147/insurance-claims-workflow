import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import event_consumer


def valid_message():
    return {
        "event_id": 7,
        "event_type": "CLAIM_SUBMITTED",
        "claim": {
            "claim_id": 12,
            "claim_number": "CLM-2026-000012",
        },
    }


def properties(headers=None):
    return SimpleNamespace(
        headers=headers or {},
        content_type="application/json",
    )


@patch("event_consumer.complete_event_processing")
@patch("event_consumer.start_event_processing")
def test_success_completes_and_acknowledges(mock_start, mock_complete):
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=101)

    event_consumer.process_message(
        channel, method, properties(), json.dumps(valid_message()).encode()
    )

    mock_start.assert_called_once_with(7, "claim_consumer")
    mock_complete.assert_called_once_with(7, "claim_consumer")
    channel.basic_ack.assert_called_once_with(delivery_tag=101)
    channel.basic_nack.assert_not_called()


@patch("event_consumer.publish_dead_letter")
def test_invalid_message_is_dead_lettered_then_acknowledged(mock_dead):
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=102)
    body = b'{"event_type":"CLAIM_SUBMITTED"}'

    event_consumer.process_message(channel, method, properties(), body)

    mock_dead.assert_called_once()
    assert mock_dead.call_args.args[1] == body
    assert "Invalid message" in mock_dead.call_args.args[3]
    channel.basic_ack.assert_called_once_with(delivery_tag=102)
    channel.basic_nack.assert_not_called()


@patch("event_consumer.publish_retry_message")
@patch("event_consumer.fail_event_processing")
@patch("event_consumer.complete_event_processing")
@patch("event_consumer.start_event_processing")
def test_processing_failure_publishes_retry_then_acknowledges(
    mock_start, mock_complete, mock_fail, mock_retry
):
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=103)
    mock_complete.side_effect = RuntimeError("Database unavailable")

    event_consumer.process_message(
        channel, method, properties(), json.dumps(valid_message()).encode()
    )

    mock_start.assert_called_once_with(7, "claim_consumer")
    mock_fail.assert_called_once()
    mock_retry.assert_called_once()
    assert mock_retry.call_args.args[3] == 1
    channel.basic_ack.assert_called_once_with(delivery_tag=103)
    channel.basic_nack.assert_not_called()


@patch("event_consumer.publish_retry_message")
@patch("event_consumer.start_event_processing")
def test_start_failure_publishes_retry(mock_start, mock_retry):
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=104)
    mock_start.side_effect = RuntimeError("Database unavailable")

    event_consumer.process_message(
        channel, method, properties(), json.dumps(valid_message()).encode()
    )

    mock_retry.assert_called_once()
    assert mock_retry.call_args.args[3] == 1
    channel.basic_ack.assert_called_once_with(delivery_tag=104)
    channel.basic_nack.assert_not_called()


@patch("event_consumer.publish_dead_letter")
@patch("event_consumer.complete_event_processing")
@patch("event_consumer.start_event_processing")
def test_exhausted_retries_go_to_dead_letter(
    mock_start, mock_complete, mock_dead
):
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=105)
    mock_complete.side_effect = RuntimeError("Still failing")

    event_consumer.process_message(
        channel,
        method,
        properties({"x-retry-count": 3}),
        json.dumps(valid_message()).encode(),
    )

    mock_dead.assert_called_once()
    assert mock_dead.call_args.kwargs["retry_count"] == 3
    channel.basic_ack.assert_called_once_with(delivery_tag=105)
    channel.basic_nack.assert_not_called()


@patch("event_consumer.publish_dead_letter")
def test_invalid_retry_header_goes_to_dead_letter(mock_dead):
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=106)
    body = json.dumps(valid_message()).encode()

    event_consumer.process_message(
        channel,
        method,
        properties({"x-retry-count": "invalid"}),
        body,
    )

    mock_dead.assert_called_once()
    channel.basic_ack.assert_called_once_with(delivery_tag=106)
    channel.basic_nack.assert_not_called()


@patch("event_consumer.publish_retry_message")
@patch("event_consumer.complete_event_processing")
@patch("event_consumer.start_event_processing")
def test_failed_retry_publish_requeues_original(
    mock_start, mock_complete, mock_retry
):
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=107)
    mock_complete.side_effect = RuntimeError("Database unavailable")
    mock_retry.side_effect = RuntimeError("Broker unavailable")

    event_consumer.process_message(
        channel, method, properties(), json.dumps(valid_message()).encode()
    )

    channel.basic_nack.assert_called_once_with(
        delivery_tag=107, requeue=True
    )
    channel.basic_ack.assert_not_called()


@patch("event_consumer.publish_dead_letter")
def test_failed_dead_letter_publish_requeues_original(mock_dead):
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=108)
    mock_dead.side_effect = RuntimeError("Broker unavailable")
    body = b'{"invalid": true}'

    event_consumer.process_message(channel, method, properties(), body)

    channel.basic_nack.assert_called_once_with(
        delivery_tag=108, requeue=True
    )
    channel.basic_ack.assert_not_called()

@patch("event_consumer.publish_dead_letter")
@patch("event_consumer.publish_retry_message")
@patch("event_consumer.fail_event_processing")
@patch("event_consumer.complete_event_processing")
@patch("event_consumer.start_event_processing")
def test_completed_duplicate_is_acknowledged_without_reprocessing(
    mock_start,
    mock_complete,
    mock_fail,
    mock_retry,
    mock_dead,
):
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=109)

    # False means this event was already completed.
    mock_start.return_value = False

    event_consumer.process_message(
        channel,
        method,
        properties(),
        json.dumps(valid_message()).encode(),
    )

    mock_start.assert_called_once_with(7, "claim_consumer")
    mock_complete.assert_not_called()
    mock_fail.assert_not_called()
    mock_retry.assert_not_called()
    mock_dead.assert_not_called()

    channel.basic_ack.assert_called_once_with(delivery_tag=109)
    channel.basic_nack.assert_not_called()
