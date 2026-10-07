import time

from services.outbox_service import publish_pending_events


POLL_INTERVAL_SECONDS = 5


def main():
    print("Outbox publisher started.")

    while True:
        try:
            published_count = publish_pending_events()

            if published_count:
                print(f"Published {published_count} pending event(s).")

        except Exception as exc:
            print(f"Outbox publisher error: {exc}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()