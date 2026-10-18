from unittest.mock import MagicMock

from services.event_queue_service import declare_event_queues
from services.event_retry_policy import (
    DEAD_LETTER_QUEUE,
    MAIN_QUEUE,
    RETRY_DELAY_MS,
    RETRY_QUEUE,
)


def test_declares_main_queue_as_durable():
    channel = MagicMock()

    declare_event_queues(channel)

    channel.queue_declare.assert_any_call(
        queue=MAIN_QUEUE,
        durable=True,
        arguments={"x-queue-type": "classic"},
    )


def test_declares_dead_letter_queue_as_durable():
    channel = MagicMock()

    declare_event_queues(channel)

    channel.queue_declare.assert_any_call(
        queue=DEAD_LETTER_QUEUE,
        durable=True,
    )


def test_declares_retry_queue_with_ttl_and_dead_letter_route():
    channel = MagicMock()

    declare_event_queues(channel)

    channel.queue_declare.assert_any_call(
        queue=RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": RETRY_DELAY_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": MAIN_QUEUE,
        },
    )


def test_declares_exactly_three_queues():
    channel = MagicMock()

    declare_event_queues(channel)

    assert channel.queue_declare.call_count == 3
