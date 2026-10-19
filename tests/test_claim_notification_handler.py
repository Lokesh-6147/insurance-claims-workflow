from unittest.mock import patch

from services.claim_notification_handler import handle_claim_notification


def submitted_event():
    return {
        "event_id": 7,
        "event_type": "CLAIM_SUBMITTED",
        "claim": {
            "claim_id": 12,
            "claim_number": "CLM-2026-000012",
        },
    }


@patch("services.claim_notification_handler.create_notification_delivery")
@patch("services.claim_notification_handler.get_claim_notification_recipient")
def test_submitted_claim_creates_pending_delivery(
    mock_recipient, mock_create
):
    mock_recipient.return_value = {
        "email": "customer@example.com",
        "claim_number": "CLM-2026-000012",
    }

    result = handle_claim_notification(submitted_event())

    assert result is True
    mock_recipient.assert_called_once_with(12)
    mock_create.assert_called_once_with(
        event_id=7,
        recipient_email="customer@example.com",
        notification_type="CLAIM_SUBMITTED",
    )


@patch("services.claim_notification_handler.create_notification_delivery")
@patch("services.claim_notification_handler.get_claim_notification_recipient")
def test_unrelated_event_does_not_create_notification(
    mock_recipient, mock_create
):
    event = submitted_event()
    event["event_type"] = "CLAIM_APPROVED"

    assert handle_claim_notification(event) is False
    mock_recipient.assert_not_called()
    mock_create.assert_not_called()


@patch("services.claim_notification_handler.get_claim_notification_recipient")
def test_missing_recipient_raises_error(mock_recipient):
    mock_recipient.return_value = None

    try:
        handle_claim_notification(submitted_event())
    except ValueError as exc:
        assert "Could not find claim recipient" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing recipient")
