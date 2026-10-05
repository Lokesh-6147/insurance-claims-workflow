import json
import os

import pika
from dotenv import load_dotenv

load_dotenv()


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

channel.queue_declare(
    queue=queue,
    durable=True,
)


def process_message(ch, method, properties, body):
    message = json.loads(body)

    print("\nReceived RabbitMQ event:")
    print(json.dumps(message, indent=2))

    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.basic_consume(
    queue=queue,
    on_message_callback=process_message,
)

print(f"Listening for messages on '{queue}'...")
print("Press CTRL+C to stop.")

channel.start_consuming()
