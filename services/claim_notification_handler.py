"""Handle claim events that require customer notifications."""

from services.notification_service import (
    create_notification_delivery,
    get_claim_notification_recipient,
)


def handle_claim_notification(event):
    """Track a pending notification for a submitted claim.

    Returns True when a delivery record exists or was created.
    Returns False when this event type does not need a notification.
    """
    if event.get("event_type") != "CLAIM_SUBMITTED":
        return False

    claim = event.get("claim")
    if not isinstance(claim, dict):
        raise ValueError("Claim details are required for notification handling.")

    claim_id = claim.get("claim_id")
    recipient = get_claim_notification_recipient(claim_id)

    if recipient is None:
        raise ValueError(f"Could not find claim recipient for claim ID {claim_id!r}.")

    create_notification_delivery(
        event_id=event["event_id"],
        recipient_email=recipient["email"],
        notification_type="CLAIM_SUBMITTED",
    )

    return True
