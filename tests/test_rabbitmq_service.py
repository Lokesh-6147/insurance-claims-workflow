
import json
from unittest.mock import MagicMock, patch

from services.rabbitmq_service import publish_claim_event

@patch.dict("os.environ", {"RABBITMQ_QUEUE": "claim_events"})
@patch("services.rabbitmq_service.pika.BlockingConnection")
def test_publish_claim_event_sends_persistent_json_message(
    mock_blocking_connection,
):
    mock_connection = MagicMock()
    mock_channel = MagicMock()

    mock_blocking_connection.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel

    claim = {
        "claim_id": 12,
        "claim_number": "CLM-2026-000012",
        "policy_id": 5,
        "incident_date": "2026-10-09",
        "claimed_amount": "15000.00",
        "status": "SUBMITTED",
    }

    publish_claim_event("CLAIM_SUBMITTED", claim)

    mock_channel.queue_declare.assert_called_once_with(
        queue="claim_events",
        durable=True,
    )

    mock_channel.basic_publish.assert_called_once()

    publish_args = mock_channel.basic_publish.call_args.kwargs
    message = json.loads(publish_args["body"])

    assert publish_args["exchange"] == ""
    assert publish_args["routing_key"] == "claim_events"
    assert message["event_type"] == "CLAIM_SUBMITTED"
    assert message["claim"]["claim_number"] == "CLM-2026-000012"
    assert message["claim"]["claimed_amount"] == "15000.00"
    assert publish_args["properties"].delivery_mode == 2

    mock_connection.close.assert_called_once()