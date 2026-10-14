
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.sla_service import SLA_DURATIONS, start_sla


@pytest.mark.parametrize("claim_id", [0, -1, True, "1", None])
def test_start_sla_rejects_invalid_claim_id(claim_id):
    connection = MagicMock()

    with pytest.raises(ValueError, match="valid claim ID"):
        start_sla(claim_id, "SUBMITTED", conn=connection)

    connection.cursor.assert_not_called()


def test_start_sla_rejects_unsupported_stage():
    connection = MagicMock()

    with pytest.raises(ValueError, match="Unsupported SLA stage"):
        start_sla(1, "UNKNOWN_STAGE", conn=connection)

    connection.cursor.assert_not_called()


def test_start_sla_uses_expected_stage_durations():
    assert SLA_DURATIONS["SUBMITTED"] == timedelta(hours=24)
    assert SLA_DURATIONS["ASSESSMENT_PENDING"] == timedelta(hours=48)
    assert SLA_DURATIONS["APPROVAL_PENDING"] == timedelta(hours=24)


def test_start_sla_does_not_insert_duplicate_active_sla():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (123,)

    start_sla(1, "SUBMITTED", conn=connection)

    assert cursor.execute.call_count == 1
    query, parameters = cursor.execute.call_args.args
    assert "sla_status = 'IN_PROGRESS'" in query
    assert parameters == (1, "SUBMITTED")


def test_start_sla_inserts_record_when_no_active_sla_exists():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None

    start_sla(1, "SUBMITTED", conn=connection)

    assert cursor.execute.call_count == 2

    insert_query, parameters = cursor.execute.call_args.args
    assert "INSERT INTO claim_sla_tracking" in insert_query
    assert parameters == (1, "SUBMITTED", timedelta(hours=24))


def test_start_sla_uses_database_connection_when_none_is_supplied():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (123,)

    with patch(
        "services.sla_service.get_db_connection",
        return_value=connection,
    ) as mock_get_db:
        start_sla(1, "SUBMITTED")

    mock_get_db.assert_called_once()

from services.sla_service import complete_sla, mark_breached_slas


def test_complete_sla_updates_active_stage():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value

    complete_sla(1, "SUBMITTED", conn=connection)

    query, parameters = cursor.execute.call_args.args
    assert "UPDATE claim_sla_tracking" in query
    assert "COMPLETED_ON_TIME" in query
    assert "BREACHED" in query
    assert parameters == (1, "SUBMITTED")


def test_mark_breached_slas_with_connection_returns_updated_count():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.rowcount = 3

    result = mark_breached_slas(conn=connection)

    assert result == 3
    query = cursor.execute.call_args.args[0]
    assert "sla_status = 'IN_PROGRESS'" in query
    assert "deadline_at < CURRENT_TIMESTAMP" in query


def test_mark_breached_slas_with_connection_returns_zero_when_none_updated():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.rowcount = 0

    result = mark_breached_slas(conn=connection)

    assert result == 0


from services.sla_service import get_claim_sla_tracking


def test_get_claim_sla_tracking_returns_history():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    expected_history = [
        (1, 10, "SUBMITTED", None, None, None, "IN_PROGRESS", None),
        (2, 10, "UNDER_REVIEW", None, None, None, "COMPLETED_ON_TIME", None),
    ]
    cursor.fetchall.return_value = expected_history

    result = get_claim_sla_tracking(10, conn=connection)

    assert result == expected_history
    query, parameters = cursor.execute.call_args.args
    assert "FROM claim_sla_tracking" in query
    assert "ORDER BY started_at ASC" in query
    assert parameters == (10,)


def test_get_claim_sla_tracking_returns_empty_list():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []

    result = get_claim_sla_tracking(10, conn=connection)

    assert result == []


@pytest.mark.parametrize("claim_id", [0, -1, True, "10", None])
def test_get_claim_sla_tracking_rejects_invalid_claim_id(claim_id):
    connection = MagicMock()

    with pytest.raises(ValueError, match="valid claim ID"):
        get_claim_sla_tracking(claim_id, conn=connection)

    connection.cursor.assert_not_called()
@patch("services.sla_service.get_db_connection")
def test_mark_breached_slas_without_connection_returns_updated_count(
    mock_get_db_connection,
):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.rowcount = 2
    mock_get_db_connection.return_value.__enter__.return_value = connection

    result = mark_breached_slas()

    assert result == 2
    mock_get_db_connection.assert_called_once()
    assert "UPDATE claim_sla_tracking" in cursor.execute.call_args.args[0]
