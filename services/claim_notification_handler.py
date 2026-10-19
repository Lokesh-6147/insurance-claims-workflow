"""Handle claim events that require customer notifications."""

from services.notification_service import (
    claim_notification_delivery,
    get_claim_notification_recipient,
    update_notification_delivery,
)
from services.ses_email_service import send_email


def handle_claim_notification(event):
    """Send a submission email once for each newly tracked delivery."""
    if event.get("event_type") != "CLAIM_SUBMITTED":
        return False

    claim = event.get("claim")
    if not isinstance(claim, dict):
        raise ValueError("Claim details are required for notification handling.")

    claim_id = claim.get("claim_id")
    recipient = get_claim_notification_recipient(claim_id)

    if recipient is None:
        raise ValueError(
            f"Could not find claim recipient for claim ID {claim_id!r}."
        )

    notification_id = claim_notification_delivery(
       event_id=event["event_id"],
       recipient_email=recipient["email"],
       notification_type="CLAIM_SUBMITTED",
    )

    # An existing delivery record must not trigger another email.
    if notification_id is None:
        return True


    subject = f"Claim {recipient['claim_number']} submitted successfully"
    body = (
        f"Hello,\n\n"
        f"We have received your insurance claim "
        f"{recipient['claim_number']}.\n\n"
        "Our team will review your submission and update you as it "
        "progresses. You can contact your insurer if you need assistance.\n\n"
        "Regards,\nInsurance Claims Team"
    )

    try:
        send_email(recipient["email"], subject, body)
    except Exception as exc:
        update_notification_delivery(notification_id, "FAILED", exc)
        raise

    update_notification_delivery(notification_id, "SENT")
    return True
