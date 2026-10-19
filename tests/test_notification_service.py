from unittest.mock import MagicMock, patch

from services.notification_service import get_claim_notification_recipient


@patch("services.notification_service.get_db_connection")
def test_get_claim_notification_recipient_returns_customer_details(
    mock_get_connection,
):
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (
        "customer@example.com",
        "CLM-12345",
    )
    mock_get_connection.return_value.__enter__.return_value = connection

    result = get_claim_notification_recipient(5)

    assert result == {
        "email": "customer@example.com",
        "claim_number": "CLM-12345",
    }

    query, params = connection.execute.call_args.args
    assert "JOIN policies AS p" in query
    assert "JOIN customers AS cu" in query
    assert params == (5,)


@patch("services.notification_service.get_db_connection")
def test_get_claim_notification_recipient_returns_none_when_claim_missing(
    mock_get_connection,
):
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = None
    mock_get_connection.return_value.__enter__.return_value = connection

    assert get_claim_notification_recipient(999999) is None


@patch("services.notification_service.get_db_connection")
def test_get_claim_notification_recipient_rejects_invalid_ids(
    mock_get_connection,
):
    for claim_id in (0, -1, "5", True, None):
        assert get_claim_notification_recipient(claim_id) is None

    mock_get_connection.assert_not_called()


@patch("services.notification_service.get_db_connection")
def test_create_notification_delivery_returns_new_id(mock_get_connection):
    from services.notification_service import create_notification_delivery

    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (42,)
    mock_get_connection.return_value.__enter__.return_value = connection

    result = create_notification_delivery(
        7, "Customer@Example.com", "CLAIM_SUBMITTED"
    )

    assert result == 42
    query, params = connection.execute.call_args.args
    assert "ON CONFLICT" in query
    assert "DO NOTHING" in query
    assert params == (7, "customer@example.com", "CLAIM_SUBMITTED")


@patch("services.notification_service.get_db_connection")
def test_create_notification_delivery_returns_none_for_duplicate(
    mock_get_connection,
):
    from services.notification_service import create_notification_delivery

    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = None
    mock_get_connection.return_value.__enter__.return_value = connection

    result = create_notification_delivery(7, "customer@example.com", "CLAIM_SUBMITTED")

    assert result is None


@patch("services.notification_service.get_db_connection")
def test_create_notification_delivery_rejects_invalid_event_id(
    mock_get_connection,
):
    from services.notification_service import create_notification_delivery

    for event_id in (0, -1, "7", True, None):
        try:
            create_notification_delivery(
                event_id, "customer@example.com", "CLAIM_SUBMITTED"
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for event_id={event_id!r}")

    mock_get_connection.assert_not_called()


@patch("services.notification_service.get_db_connection")
def test_update_notification_delivery_updates_status(mock_get_connection):
    from services.notification_service import update_notification_delivery

    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (42,)
    mock_get_connection.return_value.__enter__.return_value = connection

    result = update_notification_delivery(
        42, "FAILED", RuntimeError("Temporary delivery error")
    )

    assert result == 42
    query, params = connection.execute.call_args.args
    assert "delivery_status = %s" in query
    assert "attempt_count = attempt_count" in query
    assert "sent_at = CASE" in query
    assert params == (
        "FAILED", "FAILED", "FAILED", "FAILED",
        "Temporary delivery error", "FAILED", 42,
    )


@patch("services.notification_service.get_db_connection")
def test_update_notification_delivery_rejects_invalid_input(
    mock_get_connection,
):
    from services.notification_service import update_notification_delivery

    for notification_id in (0, -1, "42", True, None):
        try:
            update_notification_delivery(notification_id, "SENT")
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"Expected ValueError for notification_id={notification_id!r}"
            )

    for status in ("PENDING", "UNKNOWN", None):
        try:
            update_notification_delivery(42, status)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for status={status!r}")

    mock_get_connection.assert_not_called()
@patch("services.notification_service.get_db_connection")
def test_claim_notification_delivery_claims_new_delivery(mock_get_connection):
    from services.notification_service import claim_notification_delivery

    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (42,)
    mock_get_connection.return_value.__enter__.return_value = connection

    result = claim_notification_delivery(
        7, "Customer@Example.com", "CLAIM_SUBMITTED"
    )

    assert result == 42
    query, params = connection.execute.call_args.args
    assert "ON CONFLICT" in query
    assert "delivery_status = 'FAILED'" in query
    assert "RETURNING notification_id" in query
    assert params == (7, "customer@example.com", "CLAIM_SUBMITTED")


@patch("services.notification_service.get_db_connection")
def test_claim_notification_delivery_returns_none_when_not_claimable(
    mock_get_connection,
):
    from services.notification_service import claim_notification_delivery

    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = None
    mock_get_connection.return_value.__enter__.return_value = connection

    result = claim_notification_delivery(
        7, "customer@example.com", "CLAIM_SUBMITTED"
    )

    assert result is None
