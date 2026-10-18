"""Confirmed publishing for retry and dead-letter messages."""

import json

import pika

from services.event_retry_policy import (
    DEAD_LETTER_QUEUE,
    RETRY_QUEUE,
)


def publish_retry_message(channel, message, properties, retry_count):
    """Publish a persistent retry copy and return the broker confirmation."""
    headers = dict(getattr(properties, "headers", None) or {})
    headers["x-retry-count"] = retry_count

    return channel.basic_publish(
        exchange="",
        routing_key=RETRY_QUEUE,
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json",
            headers=headers,
        ),
        mandatory=True,
    )


def publish_dead_letter(channel, body, properties, reason, retry_count=None):
    """Publish the original body to the durable dead-letter queue."""
    headers = dict(getattr(properties, "headers", None) or {})
    headers["x-dead-letter-reason"] = str(reason)[:500]

    if retry_count is not None:
        headers["x-retry-count"] = retry_count

    return channel.basic_publish(
        exchange="",
        routing_key=DEAD_LETTER_QUEUE,
        body=body,
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type=getattr(properties, "content_type", None)
            or "application/json",
            headers=headers,
        ),
        mandatory=True,
    )
