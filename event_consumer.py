"""Consume claim events with processing tracking and bounded retries."""

import json
import os

import pika
from dotenv import load_dotenv

from services.event_processing_service import (
    complete_event_processing,
    fail_event_processing,
    start_event_processing,
)
from services.event_queue_service import declare_event_queues
from services.event_retry_policy import (
    MAIN_QUEUE,
    MAX_RETRIES,
    get_retry_count,
    next_retry_count,
    should_retry,
)
from services.event_retry_publisher import (
    publish_dead_letter,
    publish_retry_message,
)

load_dotenv()

CONSUMER_NAME = "claim_consumer"


def process_message(ch, method, properties, body):
    """Process a claim event with bounded retries and dead-letter routing."""

    event_id = None
    processing_started = False
    message = None

    # Step 1: Validate the message body.
    try:
        message = json.loads(body)

        if not isinstance(message, dict):
            raise ValueError("Event message must be a JSON object")

        event_id = message.get("event_id")
        if not isinstance(event_id, int) or isinstance(event_id, bool):
            raise ValueError("Event message must contain an integer event_id")

        if not message.get("event_type"):
            raise ValueError("Event message is missing event_type")

        if not isinstance(message.get("claim"), dict):
            raise ValueError("Event message is missing claim details")

    except Exception as exc:
        print(f"Invalid event message: {exc}")
        try:
            publish_dead_letter(
                ch, body, properties, f"Invalid message: {exc}"
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as publish_error:
            print(
                "Could not publish invalid message to dead-letter queue: "
                f"{publish_error}"
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return

    # Step 2: Validate the retry counter.
    try:
        retry_count = get_retry_count(properties)
    except ValueError as exc:
        try:
            publish_dead_letter(ch, body, properties, str(exc))
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as publish_error:
            print(
                "Could not dead-letter invalid retry header: "
                f"{publish_error}"
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return

    # Step 3: Track processing, skipping events already completed.
    try:
        processing_started = start_event_processing(
            event_id, CONSUMER_NAME
        )

        if not processing_started:
            print(
                f"Event {event_id} is already completed; "
                "acknowledging duplicate."
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        print("\nReceived RabbitMQ event:")
        print(json.dumps(message, indent=2))

        # Business actions such as notifications are not implemented yet.
        complete_event_processing(event_id, CONSUMER_NAME)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as exc:
        print(f"Event processing failed: {exc}")

        if processing_started:
            try:
                fail_event_processing(event_id, CONSUMER_NAME, exc)
            except Exception as status_error:
                print(
                    "Could not save FAILED processing status: "
                    f"{status_error}"
                )

        # Publish the replacement before acknowledging the original.
        try:
            if should_retry(retry_count):
                new_retry_count = next_retry_count(retry_count)
                publish_retry_message(
                    ch, message, properties, new_retry_count
                )
                print(
                    f"Retry {new_retry_count}/{MAX_RETRIES} published "
                    "to the retry queue."
                )
            else:
                publish_dead_letter(
                    ch,
                    body,
                    properties,
                    f"Processing failed after {MAX_RETRIES} retries: {exc}",
                    retry_count=retry_count,
                )
                print("Retry limit reached; event sent to dead-letter queue.")

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as publish_error:
            print(
                "Could not publish retry/dead-letter message: "
                f"{publish_error}"
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def main():
    """Connect to RabbitMQ and start consuming claim events."""

    host = os.getenv("RABBITMQ_HOST", "localhost")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))
    username = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")
    queue = os.getenv("RABBITMQ_QUEUE", MAIN_QUEUE)

    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=credentials,
    )

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Enable publisher confirms for retry/dead-letter publishing.
    channel.confirm_delivery()
    declare_event_queues(channel)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=queue,
        on_message_callback=process_message,
    )

    print(f"Waiting for events on queue '{queue}'. Press Ctrl+C to stop.")
    try:
        channel.start_consuming()
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
