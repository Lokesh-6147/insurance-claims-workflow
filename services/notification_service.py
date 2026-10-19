"""Database-backed notification delivery tracking."""

from db import get_db_connection


def get_claim_notification_recipient(claim_id):
    """Return the claim owner's email and claim number, or None."""
    if (
        not isinstance(claim_id, int)
        or isinstance(claim_id, bool)
        or claim_id <= 0
    ):
        return None

    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT cu.email, c.claim_number
            FROM claims AS c
            JOIN policies AS p
                ON p.policy_id = c.policy_id
            JOIN customers AS cu
                ON cu.customer_id = p.customer_id
            WHERE c.claim_id = %s
            """,
            (claim_id,),
        ).fetchone()

    if row is None:
        return None

    return {"email": row[0], "claim_number": row[1]}


def create_notification_delivery(event_id, recipient_email, notification_type):
    """Create a pending delivery record once per event, recipient, and type."""
    if (
        not isinstance(event_id, int)
        or isinstance(event_id, bool)
        or event_id <= 0
    ):
        raise ValueError("Event ID must be a positive integer.")

    recipient_email = recipient_email.strip().lower()
    notification_type = notification_type.strip()

    if not recipient_email or len(recipient_email) > 254:
        raise ValueError("A valid recipient email is required.")

    if not notification_type or len(notification_type) > 100:
        raise ValueError("A notification type of 1–100 characters is required.")

    with get_db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO notification_deliveries
                (event_id, recipient_email, notification_type)
            VALUES (%s, %s, %s)
            ON CONFLICT
                (event_id, recipient_email, notification_type)
            DO NOTHING
            RETURNING notification_id
            """,
            (event_id, recipient_email, notification_type),
        ).fetchone()

    return row[0] if row else None


def update_notification_delivery(notification_id, status, error=None):
    """Update delivery status, attempt count, error details, and sent time."""
    if (
        not isinstance(notification_id, int)
        or isinstance(notification_id, bool)
        or notification_id <= 0
    ):
        raise ValueError("Notification ID must be a positive integer.")

    if status not in {"SENDING", "SENT", "FAILED"}:
        raise ValueError("Unsupported notification delivery status.")

    if error is not None:
        error = str(error)[:4000]

    with get_db_connection() as connection:
        row = connection.execute(
            """
            UPDATE notification_deliveries
            SET delivery_status = %s,
                attempt_count = attempt_count
                    + CASE WHEN %s = 'SENDING' THEN 1 ELSE 0 END,
                last_error = CASE
                    WHEN %s = 'SENT' THEN NULL
                    WHEN %s = 'FAILED' THEN %s
                    ELSE last_error
                END,
                sent_at = CASE
                    WHEN %s = 'SENT' THEN CURRENT_TIMESTAMP
                    ELSE sent_at
                END
            WHERE notification_id = %s
            RETURNING notification_id
            """,
            (
                status,
                status,
                status,
                status,
                error,
                status,
                notification_id,
            ),
        ).fetchone()

    return row[0] if row else None


def claim_notification_delivery(event_id, recipient_email, notification_type):
    """Claim a new delivery or reclaim a failed delivery for retry."""
    if (
        not isinstance(event_id, int)
        or isinstance(event_id, bool)
        or event_id <= 0
    ):
        raise ValueError("Event ID must be a positive integer.")

    recipient_email = recipient_email.strip().lower()
    notification_type = notification_type.strip()

    if not recipient_email or len(recipient_email) > 254:
        raise ValueError("A valid recipient email is required.")

    if not notification_type or len(notification_type) > 100:
        raise ValueError("A notification type of 1–100 characters is required.")

    with get_db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO notification_deliveries
                (
                    event_id,
                    recipient_email,
                    notification_type,
                    delivery_status,
                    attempt_count
                )
            VALUES (%s, %s, %s, 'SENDING', 1)
            ON CONFLICT
                (event_id, recipient_email, notification_type)
            DO UPDATE SET
                delivery_status = 'SENDING',
                attempt_count = notification_deliveries.attempt_count + 1,
                last_error = NULL
            WHERE notification_deliveries.delivery_status = 'FAILED'
            RETURNING notification_id
            """,
            (event_id, recipient_email, notification_type),
        ).fetchone()

    return row[0] if row else None
