"""Helpers for bounded RabbitMQ event retries."""

MAX_RETRIES = 3
RETRY_DELAY_MS = 30_000

MAIN_QUEUE = "claim_events"
RETRY_QUEUE = "claim_events_retry"
DEAD_LETTER_QUEUE = "claim_events_dead"


def get_retry_count(properties):
    """Return the retry count from message headers."""
    headers = getattr(properties, "headers", None) or {}
    count = headers.get("x-retry-count", 0)

    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("Invalid x-retry-count header")

    return count


def should_retry(retry_count):
    """Return whether another retry is allowed."""
    return retry_count < MAX_RETRIES


def next_retry_count(retry_count):
    """Return the retry count for the next delivery."""
    if not should_retry(retry_count):
        raise ValueError("Maximum event retries exceeded")

    return retry_count + 1
