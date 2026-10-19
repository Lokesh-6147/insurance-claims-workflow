import os
from unittest.mock import patch

import pytest

from services.ses_email_service import send_email


@patch("services.ses_email_service.boto3.client")
def test_send_email_uses_ses_and_returns_message_id(mock_boto_client):
    mock_ses = mock_boto_client.return_value
    mock_ses.send_email.return_value = {"MessageId": "test-message-123"}

    with patch.dict(
        os.environ,
        {
            "SES_SENDER_EMAIL": "lokeshkadali104@gmail.com",
            "AWS_REGION": "ap-southeast-2",
        },
    ):
        result = send_email(
            "customer@example.com",
            "Claim submitted",
            "Your claim has been submitted.",
        )

    assert result == "test-message-123"
    mock_boto_client.assert_called_once_with(
        "ses", region_name="ap-southeast-2"
    )
    mock_ses.send_email.assert_called_once_with(
        Source="lokeshkadali104@gmail.com",
        Destination={"ToAddresses": ["customer@example.com"]},
        Message={
            "Subject": {"Data": "Claim submitted", "Charset": "UTF-8"},
            "Body": {
                "Text": {
                    "Data": "Your claim has been submitted.",
                    "Charset": "UTF-8",
                }
            },
        },
    )


def test_send_email_requires_sender():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="SES_SENDER_EMAIL"):
            send_email("customer@example.com", "Subject", "Body")


def test_send_email_requires_recipient():
    with patch.dict(
        os.environ, {"SES_SENDER_EMAIL": "sender@example.com"}
    ):
        with pytest.raises(ValueError, match="recipient"):
            send_email("", "Subject", "Body")
