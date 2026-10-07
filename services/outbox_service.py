

from db import get_db_connection
from services.rabbitmq_service import publish_claim_event


def publish_pending_events():
    """Publish unpublished outbox events to RabbitMQ."""

    published_count = 0

    with get_db_connection() as connection:
        events = connection.execute(
            """
            SELECT
                event_id,
                event_type,
                payload
            FROM event_outbox
            WHERE published_at IS NULL
            ORDER BY event_id
            FOR UPDATE SKIP LOCKED
            """
        ).fetchall()

        for event_id, event_type, payload in events:
            try:
                publish_claim_event(
                    event_type,
                    payload["claim"],
                )

                connection.execute(
                    """
                    UPDATE event_outbox
                    SET
                        published_at = CURRENT_TIMESTAMP,
                        publish_attempts = publish_attempts + 1,
                        last_error = NULL
                    WHERE event_id = %s
                    """,
                    (event_id,),
                )

                published_count += 1

            except Exception as exc:
                connection.execute(
                    """
                    UPDATE event_outbox
                    SET
                        publish_attempts = publish_attempts + 1,
                        last_error = %s
                    WHERE event_id = %s
                    """,
                    (str(exc), event_id),
                )

    return published_count