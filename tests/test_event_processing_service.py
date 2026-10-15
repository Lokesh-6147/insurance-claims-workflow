
from unittest.mock import MagicMock, patch

from services.event_processing_service import (
    complete_event_processing,
    fail_event_processing,
    start_event_processing,
)


@patch("services.event_processing_service.get_db_connection")
def test_start_event_processing_returns_true_for_new_or_retryable_event(
    mock_get_connection,
):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (2,)
    connection.execute.return_value = cursor
    mock_get_connection.return_value.__enter__.return_value = connection

    result = start_event_processing(2, "claim_consumer")

    query = connection.execute.call_args.args[0]
    params = connection.execute.call_args.args[1]

    assert result is True
    assert "INSERT INTO event_processing" in query
    assert "ON CONFLICT (event_id, consumer_name)" in query
    assert "WHERE event_processing.processing_status <> 'COMPLETED'" in query
    assert "RETURNING event_id" in query
    assert params == (2, "claim_consumer")


@patch("services.event_processing_service.get_db_connection")
def test_start_event_processing_returns_false_for_completed_event(
    mock_get_connection,
):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    connection.execute.return_value = cursor
    mock_get_connection.return_value.__enter__.return_value = connection

    result = start_event_processing(2, "claim_consumer")

    assert result is False


@patch("services.event_processing_service.get_db_connection")
def test_complete_event_processing(mock_get_connection):
    connection = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = connection

    complete_event_processing(2, "claim_consumer")

    query = connection.execute.call_args.args[0]
    params = connection.execute.call_args.args[1]

    assert "processing_status = 'COMPLETED'" in query
    assert "processed_at = CURRENT_TIMESTAMP" in query
    assert params == (2, "claim_consumer")


@patch("services.event_processing_service.get_db_connection")
def test_fail_event_processing(mock_get_connection):
    connection = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = connection

    fail_event_processing(
        2,
        "claim_consumer",
        RuntimeError("Test processing error"),
    )

    query = connection.execute.call_args.args[0]
    params = connection.execute.call_args.args[1]

    assert "processing_status = 'FAILED'" in query
    assert "last_error = %s" in query
    assert params == (
        "Test processing error",
        2,
        "claim_consumer",
    )


@patch("services.event_processing_service.get_db_connection")
def test_fail_event_processing_truncates_long_error(mock_get_connection):
    connection = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = connection

    long_error = "x" * 5000
    fail_event_processing(2, "claim_consumer", long_error)

    params = connection.execute.call_args.args[1]
    assert len(params[0]) == 4000
