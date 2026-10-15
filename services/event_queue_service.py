"""RabbitMQ queue declarations for claim-event retry handling."""

from services.event_retry_policy import (
    DEAD_LETTER_QUEUE,
    MAIN_QUEUE,
    RETRY_DELAY_MS,
    RETRY_QUEUE,
)


def declare_event_queues(channel):
    """Declare durable main, retry, and dead-letter queues."""

    channel.queue_declare(
        queue=MAIN_QUEUE,
        durable=True,
        arguments={"x-queue-type": "classic"},
    )

    channel.queue_declare(
        queue=DEAD_LETTER_QUEUE,
        durable=True,
    )

    channel.queue_declare(
        queue=RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": RETRY_DELAY_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": MAIN_QUEUE,
        },
    )
