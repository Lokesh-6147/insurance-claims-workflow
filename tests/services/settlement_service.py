
"""Business logic for insurance claim settlements."""

import psycopg
from decimal import Decimal, InvalidOperation

from db import get_db_connection


def create_settlement(claim_id, approved_amount, created_by=None):
    """Create one pending settlement for an approved claim."""

    # Validate claim ID.
    if (
        isinstance(claim_id, bool)
        or not isinstance(claim_id, int)
        or claim_id <= 0
    ):
        raise ValueError("A valid claim ID is required.")

    # Validate staff user ID.
    if created_by is not None and (
        isinstance(created_by, bool)
        or not isinstance(created_by, int)
        or created_by <= 0
    ):
        raise ValueError("A valid staff user ID is required.")

    # Validate settlement amount.
    try:
        amount = Decimal(str(approved_amount))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("A valid settlement amount is required.") from None

    if not amount.is_finite() or amount <= 0:
        raise ValueError(
            "The settlement amount must be greater than zero."
        )

    if amount.as_tuple().exponent < -2:
        raise ValueError(
            "The settlement amount cannot have more than two decimal places."
        )

    if amount >= Decimal("10000000000"):
        raise ValueError("The settlement amount is too large.")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Lock the claim to coordinate concurrent requests.
                cur.execute(
                    """
                    SELECT status
                    FROM claims
                    WHERE claim_id = %s
                    FOR UPDATE
                    """,
                    (claim_id,),
                )
                claim = cur.fetchone()

                if claim is None:
                    raise ValueError("Claim not found.")

                current_status = claim[0]

                # Check for an existing settlement.
                cur.execute(
                    """
                    SELECT settlement_id
                    FROM settlements
                    WHERE claim_id = %s
                    """,
                    (claim_id,),
                )

                if cur.fetchone() is not None:
                    raise ValueError(
                        "A settlement already exists for this claim."
                    )

                # Only approved claims can receive a settlement.
                if current_status != "APPROVED":
                    raise ValueError(
                        "Only approved claims can be settled."
                    )

                # Create a pending settlement.
                cur.execute(
                    """
                    INSERT INTO settlements (
                        claim_id,
                        approved_amount,
                        payment_status
                    )
                    VALUES (%s, %s, 'PENDING')
                    RETURNING settlement_id
                    """,
                    (claim_id, amount),
                )
                settlement_id = cur.fetchone()[0]

                # Update the claim status.
                cur.execute(
                    """
                    UPDATE claims
                    SET status = 'SETTLEMENT_PENDING',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE claim_id = %s
                    """,
                    (claim_id,),
                )

                # Record the status change.
                cur.execute(
                    """
                    INSERT INTO claim_status_history (
                        claim_id,
                        previous_status,
                        new_status,
                        changed_by,
                        change_reason
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        claim_id,
                        current_status,
                        "SETTLEMENT_PENDING",
                        created_by,
                        "Settlement record created; payment is pending.",
                    ),
                )

    except psycopg.errors.UniqueViolation as exc:
        # Translate the claim_id uniqueness violation into a clear message.
        if exc.diag.constraint_name == "settlements_claim_id_key":
            raise ValueError(
                "A settlement already exists for this claim."
            ) from None

        # Preserve unrelated uniqueness errors.
        raise

    return settlement_id


def process_payment(
    settlement_id,
    payment_reference,
    payment_method,
    processed_by=None,
):
    """Record payment for a pending settlement."""

    # Validate settlement ID.
    if (
        isinstance(settlement_id, bool)
        or not isinstance(settlement_id, int)
        or settlement_id <= 0
    ):
        raise ValueError("A valid settlement ID is required.")

    # Validate staff user ID.
    if processed_by is not None and (
        isinstance(processed_by, bool)
        or not isinstance(processed_by, int)
        or processed_by <= 0
    ):
        raise ValueError("A valid staff user ID is required.")

    # Validate payment reference.
    if not isinstance(payment_reference, str):
        raise ValueError("A valid payment reference is required.")

    payment_reference = payment_reference.strip()

    if not payment_reference or len(payment_reference) > 100:
        raise ValueError(
            "Payment reference must contain 1 to 100 characters."
        )

    # Validate payment method.
    allowed_methods = {"BANK_TRANSFER", "UPI", "CHEQUE"}

    if not isinstance(payment_method, str):
        raise ValueError("A valid payment method is required.")

    payment_method = payment_method.strip().upper()

    if payment_method not in allowed_methods:
        raise ValueError(
            "Payment method must be BANK_TRANSFER, UPI, or CHEQUE."
        )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Lock the settlement and associated claim.
            cur.execute(
                """
                SELECT
                    s.claim_id,
                    s.payment_status,
                    c.status
                FROM settlements s
                JOIN claims c ON c.claim_id = s.claim_id
                WHERE s.settlement_id = %s
                FOR UPDATE OF s, c
                """,
                (settlement_id,),
            )

            settlement = cur.fetchone()

            if settlement is None:
                raise ValueError("Settlement not found.")

            claim_id, payment_status, claim_status = settlement

            if payment_status != "PENDING":
                raise ValueError(
                    "Only pending settlements can be paid."
                )

            if claim_status != "SETTLEMENT_PENDING":
                raise ValueError(
                    "The claim is not awaiting settlement."
                )

            # Record the payment details.
            cur.execute(
                """
                UPDATE settlements
                SET payment_status = 'PAID',
                    payment_reference = %s,
                    payment_method = %s,
                    paid_at = CURRENT_TIMESTAMP
                WHERE settlement_id = %s
                  AND payment_status = 'PENDING'
                """,
                (
                    payment_reference,
                    payment_method,
                    settlement_id,
                ),
            )

            if cur.rowcount != 1:
                raise ValueError(
                    "Payment could not be recorded. Please retry."
                )

            # Update the claim status.
            cur.execute(
                """
                UPDATE claims
                SET status = 'SETTLED',
                    updated_at = CURRENT_TIMESTAMP
                WHERE claim_id = %s
                  AND status = 'SETTLEMENT_PENDING'
                """,
                (claim_id,),
            )

            if cur.rowcount != 1:
                raise ValueError(
                    "Claim status could not be updated."
                )

            # Record the status history.
            cur.execute(
                """
                INSERT INTO claim_status_history (
                    claim_id,
                    previous_status,
                    new_status,
                    changed_by,
                    change_reason
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    claim_id,
                    claim_status,
                    "SETTLED",
                    processed_by,
                    "Payment recorded successfully.",
                ),
            )

    return settlement_id