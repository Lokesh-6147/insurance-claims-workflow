from unittest.mock import call, patch

import pytest

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


@patch("services.claim_notification_handler.send_email")
@patch("services.claim_notification_handler.update_notification_delivery")
@patch("services.claim_notification_handler.claim_notification_delivery")
@patch("services.claim_notification_handler.get_claim_notification_recipient")
def test_submitted_claim_sends_email_and_marks_sent(
    mock_recipient, mock_create, mock_update, mock_send
):
    mock_recipient.return_value = {
        "email": "customer@example.com",
        "claim_number": "CLM-2026-000012",
    }
    mock_create.return_value = 42

    result = handle_claim_notification(submitted_event())

    assert result is True
    mock_recipient.assert_called_once_with(12)
    mock_create.assert_called_once_with(
        event_id=7,
        recipient_email="customer@example.com",
        notification_type="CLAIM_SUBMITTED",
    )
    mock_send.assert_called_once()
    assert mock_update.call_args_list == [
    call(42, "SENT")
    ]

@patch("services.claim_notification_handler.send_email")
@patch("services.claim_notification_handler.update_notification_delivery")
@patch("services.claim_notification_handler.claim_notification_delivery")
@patch("services.claim_notification_handler.get_claim_notification_recipient")
def test_duplicate_delivery_does_not_send_email(
    mock_recipient, mock_create, mock_update, mock_send
):
    mock_recipient.return_value = {
        "email": "customer@example.com",
        "claim_number": "CLM-2026-000012",
    }
    mock_create.return_value = None

    assert handle_claim_notification(submitted_event()) is True

    mock_send.assert_not_called()
    mock_update.assert_not_called()


@patch("services.claim_notification_handler.send_email")
@patch("services.claim_notification_handler.update_notification_delivery")
@patch("services.claim_notification_handler.claim_notification_delivery")
@patch("services.claim_notification_handler.get_claim_notification_recipient")
def test_email_failure_marks_failed_and_reraises(
    mock_recipient, mock_create, mock_update, mock_send
):
    mock_recipient.return_value = {
        "email": "customer@example.com",
        "claim_number": "CLM-2026-000012",
    }
    mock_create.return_value = 42
    mock_send.side_effect = RuntimeError("SES unavailable")

    with pytest.raises(RuntimeError, match="SES unavailable"):
        handle_claim_notification(submitted_event())

    assert mock_update.call_args_list == [
    call(42, "FAILED", mock_send.side_effect)
    ]


@patch("services.claim_notification_handler.claim_notification_delivery")
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

    with pytest.raises(ValueError, match="Could not find claim recipient"):
        handle_claim_notification(submitted_event())
