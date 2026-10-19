"""Send customer notification emails through Amazon SES."""

import os

import boto3


def send_email(recipient_email, subject, body_text):
    """Send a plain-text email using the configured Amazon SES identity."""
    sender_email = os.getenv("SES_SENDER_EMAIL")
    aws_region = os.getenv("AWS_REGION", "ap-southeast-2")

    if not sender_email:
        raise RuntimeError("SES_SENDER_EMAIL is not configured.")

    if not recipient_email or not recipient_email.strip():
        raise ValueError("A recipient email address is required.")

    client = boto3.client("ses", region_name=aws_region)
    response = client.send_email(
        Source=sender_email,
        Destination={"ToAddresses": [recipient_email.strip()]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": body_text, "Charset": "UTF-8"}
            },
        },
    )

    return response["MessageId"]
