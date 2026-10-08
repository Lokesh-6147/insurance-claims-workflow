from datetime import timedelta

from psycopg import connection

from db import get_db_connection


# SLA duration for each claim-processing stage.
SLA_DURATIONS = {
    "SUBMITTED": timedelta(hours=24),
    "UNDER_REVIEW": timedelta(hours=24),
    "ASSESSMENT_PENDING": timedelta(hours=48),
    "APPROVAL_PENDING": timedelta(hours=24),
    "SETTLEMENT_PENDING": timedelta(hours=24),
}

def start_sla(claim_id, stage_name, conn=None):
    """Start an SLA timer for a claim-processing stage."""

    if (
        isinstance(claim_id, bool)
        or not isinstance(claim_id, int)
        or claim_id <= 0
    ):
        raise ValueError("A valid claim ID is required.")

    if stage_name not in SLA_DURATIONS:
        raise ValueError(f"Unsupported SLA stage: {stage_name}")

    duration = SLA_DURATIONS[stage_name]

    connection = conn or get_db_connection()

    with connection.cursor() as cur:
        # Do not create duplicate active SLA records
        # for the same claim and stage.
        cur.execute(
            """
            SELECT sla_tracking_id
            FROM claim_sla_tracking
            WHERE claim_id = %s
              AND stage_name = %s
              AND sla_status = 'IN_PROGRESS'
            """,
            (claim_id, stage_name),
        )

        if cur.fetchone() is not None:
            return

        cur.execute(
            """
            INSERT INTO claim_sla_tracking (
                claim_id,
                stage_name,
                started_at,
                deadline_at,
                sla_status
            )
            VALUES (
                %s,
                %s,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP + %s,
                'IN_PROGRESS'
            )
            """,
            (claim_id, stage_name, duration),
        )


def complete_sla(claim_id, stage_name, conn=None):
    """Complete the active SLA for a claim stage."""

    connection = conn or get_db_connection()

    with connection.cursor() as cur:
        cur.execute(
            """
            UPDATE claim_sla_tracking
            SET completed_at = CURRENT_TIMESTAMP,
                sla_status = CASE
                    WHEN CURRENT_TIMESTAMP <= deadline_at
                    THEN 'COMPLETED_ON_TIME'
                    ELSE 'BREACHED'
                END
            WHERE claim_id = %s
              AND stage_name = %s
              AND sla_status = 'IN_PROGRESS'
            """,
            (claim_id, stage_name),
        )

def mark_breached_slas(conn=None):
    """Mark all overdue active SLAs as breached."""

    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE claim_sla_tracking
                SET sla_status = 'BREACHED'
                WHERE sla_status = 'IN_PROGRESS'
                  AND deadline_at < CURRENT_TIMESTAMP
                """
            )

            return cur.rowcount

    with get_db_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE claim_sla_tracking
                SET sla_status = 'BREACHED'
                WHERE sla_status = 'IN_PROGRESS'
                  AND deadline_at < CURRENT_TIMESTAMP
                """
            )

            return cur.rowcount

def get_claim_sla_tracking(claim_id, conn=None):
    """Return SLA tracking history for a claim."""

    if (
        isinstance(claim_id, bool)
        or not isinstance(claim_id, int)
        or claim_id <= 0
    ):
        raise ValueError("A valid claim ID is required.")

    connection = conn or get_db_connection()

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT
                sla_tracking_id,
                claim_id,
                stage_name,
                started_at,
                deadline_at,
                completed_at,
                sla_status,
                created_at
            FROM claim_sla_tracking
            WHERE claim_id = %s
            ORDER BY started_at ASC
            """,
            (claim_id,),
        )

        return cur.fetchall()