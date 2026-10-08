
import secrets
from datetime import date

from db import get_db_connection


def create_policy(
    customer_id,
    vehicle_id,
    coverage_details,
    premium_amount,
    start_date,
    expiry_date,
):
    """Create an insurance policy for a customer's registered vehicle."""

    coverage_details = coverage_details.strip()

    if not coverage_details:
        raise ValueError("Coverage details are required.")

    try:
        premium_amount = float(premium_amount)
    except (TypeError, ValueError):
        raise ValueError("Premium amount must be a valid number.")

    if not 0 <= premium_amount < 1_000_000_000:
        raise ValueError("Premium amount must be non-negative and valid.")

    try:
        start_date = date.fromisoformat(start_date)
        expiry_date = date.fromisoformat(expiry_date)
    except (TypeError, ValueError):
        raise ValueError("Enter valid policy dates in YYYY-MM-DD format.")

    if expiry_date <= start_date:
        raise ValueError("Expiry date must be after the start date.")

    policy_number = f"POL-{secrets.token_hex(6).upper()}"

    with get_db_connection() as connection:
        with connection.transaction():
            vehicle = connection.execute(
                """
                SELECT vehicle_id
                FROM vehicles
                WHERE vehicle_id = %s
                  AND customer_id = %s
                """,
                (vehicle_id, customer_id),
            ).fetchone()

            if vehicle is None:
                raise ValueError(
                    "The selected vehicle does not belong to your account."
                )

            policy = connection.execute(
                """
                INSERT INTO policies (
                    policy_number,
                    customer_id,
                    vehicle_id,
                    coverage_details,
                    premium_amount,
                    start_date,
                    expiry_date,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    policy_id,
                    policy_number,
                    customer_id,
                    vehicle_id,
                    coverage_details,
                    premium_amount,
                    start_date,
                    expiry_date,
                    status
                """,
                (
                    policy_number,
                    customer_id,
                    vehicle_id,
                    coverage_details,
                    premium_amount,
                    start_date,
                    expiry_date,
                    "PENDING",
                ),
            ).fetchone()

    return {
        "policy_id": policy[0],
        "policy_number": policy[1],
        "customer_id": policy[2],
        "vehicle_id": policy[3],
        "coverage_details": policy[4],
        "premium_amount": policy[5],
        "start_date": policy[6],
        "expiry_date": policy[7],
        "status": policy[8],
    }


def get_customer_policies(customer_id):
    """Return policies belonging to a specific customer."""

    with get_db_connection() as connection:
        policies = connection.execute(
            """
            SELECT
                p.policy_id,
                p.policy_number,
                p.vehicle_id,
                v.registration_number,
                v.make,
                v.model,
                p.coverage_details,
                p.premium_amount,
                p.start_date,
                p.expiry_date,
                p.status
            FROM policies AS p
            JOIN vehicles AS v
                ON p.vehicle_id = v.vehicle_id
            WHERE p.customer_id = %s
            ORDER BY p.created_at DESC
            """,
            (customer_id,),
        ).fetchall()

    return [
        {
            "policy_id": policy[0],
            "policy_number": policy[1],
            "vehicle_id": policy[2],
            "registration_number": policy[3],
            "make": policy[4],
            "model": policy[5],
            "coverage_details": policy[6],
            "premium_amount": policy[7],
            "start_date": policy[8],
            "expiry_date": policy[9],
            "status": policy[10],
        }
        for policy in policies
    ]


def get_pending_policies():
    """Return all policies that are waiting for staff approval."""

    with get_db_connection() as connection:
        policies = connection.execute(
            """
            SELECT
                p.policy_id,
                p.policy_number,
                p.customer_id,
                c.account_id,
                c.full_name,
                p.vehicle_id,
                v.registration_number,
                v.make,
                v.model,
                p.coverage_details,
                p.premium_amount,
                p.start_date,
                p.expiry_date,
                p.status,
                p.created_at
            FROM policies AS p
            JOIN customers AS c
                ON p.customer_id = c.customer_id
            JOIN vehicles AS v
                ON p.vehicle_id = v.vehicle_id
            WHERE p.status = 'PENDING'
            ORDER BY p.created_at ASC
            """
        ).fetchall()

    return [
        {
            "policy_id": policy[0],
            "policy_number": policy[1],
            "customer_id": policy[2],
            "account_id": policy[3],
            "customer_name": policy[4],
            "vehicle_id": policy[5],
            "registration_number": policy[6],
            "make": policy[7],
            "model": policy[8],
            "coverage_details": policy[9],
            "premium_amount": policy[10],
            "start_date": policy[11],
            "expiry_date": policy[12],
            "status": policy[13],
            "created_at": policy[14],
        }
        for policy in policies
    ]


def get_policy_by_id(policy_id):
    """Return complete policy details for staff review."""

    with get_db_connection() as connection:
        policy = connection.execute(
            """
            SELECT
                p.policy_id,
                p.policy_number,
                p.customer_id,
                c.account_id,
                c.full_name,
                p.vehicle_id,
                v.registration_number,
                v.make,
                v.model,
                p.coverage_details,
                p.premium_amount,
                p.start_date,
                p.expiry_date,
                p.status,
                p.created_at
            FROM policies AS p
            JOIN customers AS c
                ON p.customer_id = c.customer_id
            JOIN vehicles AS v
                ON p.vehicle_id = v.vehicle_id
            WHERE p.policy_id = %s
            """,
            (policy_id,),
        ).fetchone()

    if policy is None:
        return None

    return {
        "policy_id": policy[0],
        "policy_number": policy[1],
        "customer_id": policy[2],
        "account_id": policy[3],
        "customer_name": policy[4],
        "vehicle_id": policy[5],
        "registration_number": policy[6],
        "make": policy[7],
        "model": policy[8],
        "coverage_details": policy[9],
        "premium_amount": policy[10],
        "start_date": policy[11],
        "expiry_date": policy[12],
        "status": policy[13],
        "created_at": policy[14],
    }


def approve_policy(policy_id):
    """Approve a pending policy and change its status to ACTIVE."""

    with get_db_connection() as connection:
        with connection.transaction():
            policy = connection.execute(
                """
                SELECT policy_id, policy_number, status
                FROM policies
                WHERE policy_id = %s
                FOR UPDATE
                """,
                (policy_id,),
            ).fetchone()

            if policy is None:
                raise ValueError("Policy not found.")

            if policy[2] != "PENDING":
                raise ValueError(
                    f"Policy {policy[1]} cannot be approved because "
                    f"its current status is {policy[2]}."
                )

            updated_policy = connection.execute(
                """
                UPDATE policies
                SET status = 'ACTIVE'
                WHERE policy_id = %s
                RETURNING
                    policy_id,
                    policy_number,
                    customer_id,
                    vehicle_id,
                    coverage_details,
                    premium_amount,
                    start_date,
                    expiry_date,
                    status
                """,
                (policy_id,),
            ).fetchone()

    return {
        "policy_id": updated_policy[0],
        "policy_number": updated_policy[1],
        "customer_id": updated_policy[2],
        "vehicle_id": updated_policy[3],
        "coverage_details": updated_policy[4],
        "premium_amount": updated_policy[5],
        "start_date": updated_policy[6],
        "expiry_date": updated_policy[7],
        "status": updated_policy[8],
    }


def reject_policy(policy_id):
    """Reject a pending policy and change its status to REJECTED."""

    with get_db_connection() as connection:
        with connection.transaction():
            policy = connection.execute(
                """
                SELECT policy_id, policy_number, status
                FROM policies
                WHERE policy_id = %s
                FOR UPDATE
                """,
                (policy_id,),
            ).fetchone()

            if policy is None:
                raise ValueError("Policy not found.")

            if policy[2] != "PENDING":
                raise ValueError(
                    f"Policy {policy[1]} cannot be rejected because "
                    f"its current status is {policy[2]}."
                )

            updated_policy = connection.execute(
                """
                UPDATE policies
                SET status = 'REJECTED'
                WHERE policy_id = %s
                RETURNING
                    policy_id,
                    policy_number,
                    customer_id,
                    vehicle_id,
                    coverage_details,
                    premium_amount,
                    start_date,
                    expiry_date,
                    status
                """,
                (policy_id,),
            ).fetchone()

    return {
        "policy_id": updated_policy[0],
        "policy_number": updated_policy[1],
        "customer_id": updated_policy[2],
        "vehicle_id": updated_policy[3],
        "coverage_details": updated_policy[4],
        "premium_amount": updated_policy[5],
        "start_date": updated_policy[6],
        "expiry_date": updated_policy[7],
        "status": updated_policy[8],
    }


def get_customer_claimable_policies(customer_id):
    """Return active policies that are valid today for this customer."""

    with get_db_connection() as connection:
        policies = connection.execute(
            """
            SELECT
                p.policy_id,
                p.policy_number,
                p.vehicle_id,
                v.registration_number,
                v.make,
                v.model,
                p.start_date,
                p.expiry_date
            FROM policies AS p
            JOIN vehicles AS v
                ON p.vehicle_id = v.vehicle_id
            WHERE p.customer_id = %s
              AND p.status = 'ACTIVE'
              AND p.start_date <= CURRENT_DATE
              AND p.expiry_date >= CURRENT_DATE
            ORDER BY p.created_at DESC
            """,
            (customer_id,),
        ).fetchall()

    return [
        {
            "policy_id": policy[0],
            "policy_number": policy[1],
            "vehicle_id": policy[2],
            "registration_number": policy[3],
            "make": policy[4],
            "model": policy[5],
            "start_date": policy[6],
            "expiry_date": policy[7],
        }
        for policy in policies
    ]

