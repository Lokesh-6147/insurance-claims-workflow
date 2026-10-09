import json
import os

import pika
from dotenv import load_dotenv

load_dotenv()


def publish_claim_event(event_type, claim):
    """Publish a claim event to RabbitMQ."""

    host = os.getenv("RABBITMQ_HOST", "localhost")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))
    username = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")
    queue = os.getenv("RABBITMQ_QUEUE", "claim_events")

    credentials = pika.PlainCredentials(username, password)

    parameters = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=credentials,
    )

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.confirm_delivery()

    channel.queue_declare(
        queue=queue,
        durable=True,
    )

    message = {
        "event_type": event_type,
        "claim": {
            "claim_id": claim.get("claim_id"),
            "claim_number": claim.get("claim_number"),
            "policy_id": claim.get("policy_id"),
            "incident_date": str(claim.get("incident_date")),
            "claimed_amount": str(claim.get("claimed_amount")),
            "status": claim.get("status"),
        },
    }

    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json",
        ),
    )

    connection.close()
