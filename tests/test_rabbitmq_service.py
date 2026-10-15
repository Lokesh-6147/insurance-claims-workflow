
import json
from unittest.mock import MagicMock, patch

import pytest

from services.rabbitmq_service import publish_claim_event


@pytest.fixture
def mock_rabbitmq():
    with patch.dict("os.environ", {"RABBITMQ_QUEUE": "claim_events"}):
        with patch(
            "services.rabbitmq_service.pika.BlockingConnection"
        ) as mock_blocking_connection:
            mock_connection = MagicMock()
            mock_channel = MagicMock()

            mock_blocking_connection.return_value = mock_connection
            mock_connection.channel.return_value = mock_channel
            mock_connection.is_open = True

            yield mock_blocking_connection, mock_connection, mock_channel


@pytest.fixture
def sample_claim():
    return {
        "claim_id": 12,
        "claim_number": "CLM-2026-000012",
        "policy_id": 5,
        "incident_date": "2026-10-09",
        "claimed_amount": "15000.00",
        "status": "SUBMITTED",
    }


def test_publish_claim_event_sends_persistent_json_message(
    mock_rabbitmq,
    sample_claim,
):
    mock_blocking_connection, mock_connection, mock_channel = mock_rabbitmq

    publish_claim_event(
        "CLAIM_SUBMITTED",
        sample_claim,
        event_id=7,
    )

    mock_blocking_connection.assert_called_once()
    mock_connection.channel.assert_called_once_with()

    mock_channel.confirm_delivery.assert_called_once_with()

    mock_channel.queue_declare.assert_called_once_with(
        queue="claim_events",
        durable=True,
    )

    mock_channel.basic_publish.assert_called_once()

    publish_args = mock_channel.basic_publish.call_args.kwargs
    message = json.loads(publish_args["body"])

    assert publish_args["exchange"] == ""
    assert publish_args["routing_key"] == "claim_events"
    assert publish_args["mandatory"] is True

    assert message["event_id"] == 7
    assert message["event_type"] == "CLAIM_SUBMITTED"
    assert message["claim"]["claim_number"] == "CLM-2026-000012"
    assert message["claim"]["claimed_amount"] == "15000.00"

    assert publish_args["properties"].delivery_mode == 2
    assert publish_args["properties"].content_type == "application/json"

    mock_connection.close.assert_called_once_with()


def test_publish_claim_event_closes_connection_when_publish_fails(
    mock_rabbitmq,
    sample_claim,
):
    _, mock_connection, mock_channel = mock_rabbitmq
    mock_channel.basic_publish.side_effect = RuntimeError(
        "RabbitMQ publish failed"
    )

    with pytest.raises(RuntimeError, match="RabbitMQ publish failed"):
        publish_claim_event(
            "CLAIM_SUBMITTED",
            sample_claim,
            event_id=8,
        )

    mock_channel.confirm_delivery.assert_called_once_with()
    mock_channel.basic_publish.assert_called_once()
    mock_connection.close.assert_called_once_with()


def test_publish_claim_event_closes_connection_when_queue_declaration_fails(
    mock_rabbitmq,
    sample_claim,
):
    _, mock_connection, mock_channel = mock_rabbitmq
    mock_channel.queue_declare.side_effect = RuntimeError(
        "Queue declaration failed"
    )

    with pytest.raises(RuntimeError, match="Queue declaration failed"):
        publish_claim_event(
            "CLAIM_SUBMITTED",
            sample_claim,
            event_id=9,
        )

    mock_channel.basic_publish.assert_not_called()
    mock_connection.close.assert_called_once_with()
