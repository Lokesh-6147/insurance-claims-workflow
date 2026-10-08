import time

from services.sla_service import mark_breached_slas


POLL_INTERVAL_SECONDS = 60


def main():
    print("SLA worker started.")

    while True:
        try:
            breached_count = mark_breached_slas()

            if breached_count:
                print(
                    f"Marked {breached_count} overdue SLA(s) as breached."
                )

        except Exception as exc:
            print(f"SLA worker error: {exc}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()