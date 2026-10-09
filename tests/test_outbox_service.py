from unittest.mock import MagicMock, patch

from services.outbox_service import publish_pending_events


@patch("services.outbox_service.publish_claim_event")
@patch("services.outbox_service.get_db_connection")
def test_publish_pending_event_marks_it_as_published(
    mock_get_connection, mock_publish
):
    connection = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = connection
    claim = {"claim_id": 12, "claim_number": "CLM-TEST-12"}
    connection.execute.return_value.fetchall.return_value = [
        (1, "CLAIM_SUBMITTED", {"claim": claim})
    ]

    result = publish_pending_events()

    assert result == 1
    mock_publish.assert_called_once_with("CLAIM_SUBMITTED", claim)
    update_call = connection.execute.call_args_list[1]
    assert "published_at = CURRENT_TIMESTAMP" in update_call.args[0]
    assert update_call.args[1] == (1,)


@patch("services.outbox_service.publish_claim_event")
@patch("services.outbox_service.get_db_connection")
def test_publish_failure_records_error(
    mock_get_connection, mock_publish
):
    connection = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = connection
    connection.execute.return_value.fetchall.return_value = [
        (2, "CLAIM_SUBMITTED", {"claim": {"claim_id": 13}})
    ]
    mock_publish.side_effect = RuntimeError("RabbitMQ unavailable")

    result = publish_pending_events()

    assert result == 0
    update_call = connection.execute.call_args_list[1]
    assert "last_error = %s" in update_call.args[0]
    assert update_call.args[1] == ("RabbitMQ unavailable", 2)
