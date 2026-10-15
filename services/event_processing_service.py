
"""Track claim-event processing and avoid reprocessing completed events."""

from db import get_db_connection


def start_event_processing(event_id, consumer_name):
    """Claim an event for processing; return False if already completed."""
    with get_db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO event_processing (
                event_id,
                consumer_name,
                processing_status,
                processing_attempts,
                received_at,
                processed_at,
                last_error
            )
            VALUES (%s, %s, 'PROCESSING', 1, CURRENT_TIMESTAMP, NULL, NULL)
            ON CONFLICT (event_id, consumer_name)
            DO UPDATE SET
                processing_status = 'PROCESSING',
                processing_attempts =
                    event_processing.processing_attempts + 1,
                received_at = CURRENT_TIMESTAMP,
                processed_at = NULL,
                last_error = NULL
            WHERE event_processing.processing_status <> 'COMPLETED'
            RETURNING event_id
            """,
            (event_id, consumer_name),
        )
        return cursor.fetchone() is not None


def complete_event_processing(event_id, consumer_name):
    """Mark an event as successfully processed."""
    with get_db_connection() as connection:
        connection.execute(
            """
            UPDATE event_processing
            SET processing_status = 'COMPLETED',
                processed_at = CURRENT_TIMESTAMP,
                last_error = NULL
            WHERE event_id = %s
              AND consumer_name = %s
            """,
            (event_id, consumer_name),
        )


def fail_event_processing(event_id, consumer_name, error):
    """Record an event-processing failure."""
    with get_db_connection() as connection:
        connection.execute(
            """
            UPDATE event_processing
            SET processing_status = 'FAILED',
                processed_at = NULL,
                last_error = %s
            WHERE event_id = %s
              AND consumer_name = %s
            """,
            (str(error)[:4000], event_id, consumer_name),
        )
