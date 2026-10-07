
import secrets
from datetime import date
from decimal import Decimal, InvalidOperation

from db import get_db_connection
from services.rabbitmq_service import publish_claim_event
from services.rules_service import (
    evaluate_claim_rules,
    save_rule_evaluations,
    save_fraud_flags,
)

def register_claim(
    customer_id,
    policy_id,
    incident_date,
    incident_description,
    claimed_amount,
):
    """Register a claim against an eligible customer policy."""

    # 1. Validate customer and policy IDs.
    if (
        not isinstance(customer_id, int)
        or isinstance(customer_id, bool)
        or customer_id <= 0
    ):
        raise ValueError("Invalid customer account.")

    if (
        not isinstance(policy_id, int)
        or isinstance(policy_id, bool)
        or policy_id <= 0
    ):
        raise ValueError("Please select a valid insurance policy.")

    # 2. Validate the incident description.
    if not isinstance(incident_description, str):
        raise ValueError("Incident description is required.")

    incident_description = incident_description.strip()

    if not incident_description:
        raise ValueError("Incident description is required.")

    if len(incident_description) > 5000:
        raise ValueError(
            "Incident description must be 5000 characters or fewer."
        )

    # 3. Validate the incident date.
    try:
        incident_date = date.fromisoformat(str(incident_date))
    except (TypeError, ValueError):
        raise ValueError(
            "Enter a valid incident date in YYYY-MM-DD format."
        )

    if incident_date > date.today():
        raise ValueError("Incident date cannot be in the future.")

    # 4. Validate the claimed amount.
    try:
        claimed_amount = Decimal(str(claimed_amount))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Claimed amount must be a valid number.")

    if not claimed_amount.is_finite() or claimed_amount <= 0:
        raise ValueError("Claimed amount must be greater than zero.")

    if claimed_amount.as_tuple().exponent < -2:
        raise ValueError(
            "Claimed amount can have at most two decimal places."
        )

    if claimed_amount >= Decimal("10000000000"):
        raise ValueError("Claimed amount is too large.")

    # 5. Generate a claim reference number.
    claim_number = f"CLM-{secrets.token_hex(6).upper()}"

    # 6. Verify policy eligibility and create the claim atomically.
    with get_db_connection() as connection:
        with connection.transaction():

            policy = connection.execute(
                """
                SELECT policy_id, start_date
                FROM policies
                WHERE policy_id = %s
                  AND customer_id = %s
                  AND status = 'ACTIVE'
                  AND start_date <= %s
                  AND expiry_date >= %s
                FOR UPDATE
                """,
                (
                    policy_id,
                    customer_id,
                    incident_date,
                    incident_date,
                ),
            ).fetchone()

            if policy is None:
                raise ValueError(
                    "The selected policy is not eligible for this claim. "
                    "Check policy ownership, status, and coverage dates."
                )

            # 7. Insert the claim.
            claim = connection.execute(
                """
                INSERT INTO claims (
                    claim_number,
                    policy_id,
                    incident_date,
                    incident_description,
                    claimed_amount,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING
                    claim_id,
                    claim_number,
                    policy_id,
                    incident_date,
                    incident_description,
                    claimed_amount,
                    status,
                    created_at
                """,
                (
                    claim_number,
                    policy_id,
                    incident_date,
                    incident_description,
                    claimed_amount,
                    "SUBMITTED",
                ),
            ).fetchone()

            # 8. Evaluate configurable claim rules.
            rule_evaluation = evaluate_claim_rules(
                customer_id=customer_id,
                claimed_amount=claimed_amount,
                policy_start_date=policy[1],
                incident_date=incident_date,
            )

            # Save rule evaluation results in the same transaction.
            save_rule_evaluations(
                connection,
                claim[0],
                rule_evaluation,
            )

            # Save detected fraud flags in the same transaction.
            save_fraud_flags(
                connection,
                claim[0],
                rule_evaluation,
            )

            # 9. Record the initial status in the history table.
            connection.execute(
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
                    claim[0],
                    None,
                    "SUBMITTED",
                    None,
                    "Initial claim submission",
                ),
            )

    # 9. Publish the claim submission event after the database transaction succeeds.
    new_claim = {
        "claim_id": claim[0],
        "claim_number": claim[1],
        "policy_id": claim[2],
        "incident_date": claim[3],
        "incident_description": claim[4],
        "claimed_amount": claim[5],
        "status": claim[6],
        "created_at": claim[7],
    }
    publish_claim_event("CLAIM_SUBMITTED", new_claim)
    return new_claim

def get_customer_claims(customer_id):
    """Return claims belonging to a specific customer."""

    with get_db_connection() as connection:
        claims = connection.execute(
            """
            SELECT
                c.claim_id,
                c.claim_number,
                c.policy_id,
                p.policy_number,
                c.incident_date,
                c.incident_description,
                c.claimed_amount,
                c.status,
                c.created_at
            FROM claims AS c
            JOIN policies AS p
                ON c.policy_id = p.policy_id
            WHERE p.customer_id = %s
            ORDER BY c.created_at DESC
            """,
            (customer_id,),
        ).fetchall()

    return [
        {
            "claim_id": claim[0],
            "claim_number": claim[1],
            "policy_id": claim[2],
            "policy_number": claim[3],
            "incident_date": claim[4],
            "incident_description": claim[5],
            "claimed_amount": claim[6],
            "status": claim[7],
            "created_at": claim[8],
        }
        for claim in claims
    ]

def get_customer_claim_details(customer_id, claim_id):
    """Return one claim only if it belongs to the specified customer."""

    with get_db_connection() as connection:
        claim = connection.execute(
            """
            SELECT
                c.claim_id,
                c.claim_number,
                c.policy_id,
                p.policy_number,
                c.incident_date,
                c.incident_description,
                c.claimed_amount,
                c.status,
                c.fraud_risk_level,
                c.sla_deadline,
                c.created_at,
                c.updated_at
            FROM claims AS c
            JOIN policies AS p
                ON c.policy_id = p.policy_id
            WHERE p.customer_id = %s
              AND c.claim_id = %s
            """,
            (customer_id, claim_id),
        ).fetchone()

    if claim is None:
        return None

    return {
        "claim_id": claim[0],
        "claim_number": claim[1],
        "policy_id": claim[2],
        "policy_number": claim[3],
        "incident_date": claim[4],
        "incident_description": claim[5],
        "claimed_amount": claim[6],
        "status": claim[7],
        "fraud_risk_level": claim[8],
        "sla_deadline": claim[9],
        "created_at": claim[10],
        "updated_at": claim[11],
    }

def get_staff_claim_queue():
    """Return claims for authorized staff to review."""

    with get_db_connection() as connection:
        claims = connection.execute(
            """
            SELECT
                c.claim_id,
                c.claim_number,
                p.policy_number,
                c.incident_date,
                c.claimed_amount,
                c.status,
                c.fraud_risk_level,
                c.created_at
            FROM claims AS c
            JOIN policies AS p
                ON p.policy_id = c.policy_id
            ORDER BY
                c.created_at ASC,
                c.claim_id ASC
            """
        ).fetchall()

    return [
        {
            "claim_id": claim[0],
            "claim_number": claim[1],
            "policy_number": claim[2],
            "incident_date": claim[3],
            "claimed_amount": claim[4],
            "status": claim[5],
            "fraud_risk_level": claim[6],
            "created_at": claim[7],
        }
        for claim in claims
    ]


def get_staff_claim_details(claim_id):
    """Return claim details, including settlement information, for staff."""
    if not isinstance(claim_id, int) or isinstance(claim_id, bool) or claim_id <= 0:
        return None

    query = """
        SELECT
            c.claim_id,
            c.claim_number,
            c.policy_id,
            p.policy_number,
            c.incident_date,
            c.incident_description,
            c.claimed_amount,
            c.status,
            c.fraud_risk_level,
            c.fraud_risk_score,
            c.sla_deadline,
            c.created_at,
            c.updated_at,
            s.settlement_id,
            s.approved_amount,
            s.payment_status,
            s.payment_reference,
            s.payment_method,
            s.created_at AS settlement_created_at,
            s.paid_at
        FROM claims c
        JOIN policies p
            ON p.policy_id = c.policy_id
        LEFT JOIN settlements s
            ON s.claim_id = c.claim_id
        WHERE c.claim_id = %s;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (claim_id,))
            row = cur.fetchone()

            if row is None:
                return None

            columns = [column.name for column in cur.description]
            return dict(zip(columns, row))
        
def create_claim_assessment(
    claim_id,
    assessor_id,
    damage_description,
    estimated_repair_cost,
    recommendation,
    assessment_notes=None,
):
    """Save an assessment for a claim."""
    allowed_recommendations = {
        "RECOMMEND_APPROVAL",
        "RECOMMEND_REJECTION",
        "MORE_INFORMATION_REQUIRED",
    }

    if not isinstance(claim_id, int) or claim_id <= 0:
        raise ValueError("Invalid claim ID.")

    if not isinstance(assessor_id, int) or assessor_id <= 0:
        raise ValueError("Invalid assessor ID.")

    if not isinstance(damage_description, str) or not damage_description.strip():
        raise ValueError("Damage description is required.")

    if len(damage_description.strip()) > 5000:
        raise ValueError("Damage description is too long.")

    if recommendation not in allowed_recommendations:
        raise ValueError("Invalid assessment recommendation.")

    if assessment_notes is not None:
        if not isinstance(assessment_notes, str):
            raise ValueError("Assessment notes must be text.")
        if len(assessment_notes) > 5000:
            raise ValueError("Assessment notes are too long.")

    try:
        repair_cost = Decimal(str(estimated_repair_cost))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Estimated repair cost must be a valid number.")

    if not repair_cost.is_finite() or repair_cost < 0:
        raise ValueError("Estimated repair cost cannot be negative.")

    if repair_cost.as_tuple().exponent < -2:
        raise ValueError("Estimated repair cost supports up to two decimal places.")

    if repair_cost >= Decimal("10000000000"):
        raise ValueError("Estimated repair cost is too large.")

    
    query = """
        SELECT
            c.claim_id,
            c.claim_number,
            c.policy_id,
            p.policy_number,
            c.incident_date,
            c.incident_description,
            c.claimed_amount,
            c.status,
            c.fraud_risk_level,
            c.fraud_risk_score,
            c.sla_deadline,
            c.created_at,
            c.updated_at,
            s.settlement_id,
            s.approved_amount,
            s.payment_status,
            s.payment_reference,
            s.payment_method,
            s.created_at AS settlement_created_at,
            s.paid_at
        FROM claims c
        JOIN policies p
            ON p.policy_id = c.policy_id
        LEFT JOIN settlements s
            ON s.claim_id = c.claim_id
        WHERE c.claim_id = %s;
    """

    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Lock the claim while the assessment is processed.
            cur.execute(
                """
                SELECT status
                FROM claims
                WHERE claim_id = %s
                FOR UPDATE;
                """,
                (claim_id,),
            )
            claim = cur.fetchone()

            if claim is None:
                raise ValueError("Claim not found.")

            previous_status = claim[0]

            allowed_statuses = {
                "SUBMITTED",
                "UNDER_REVIEW",
                "ASSESSMENT_PENDING",
            }

            if previous_status not in allowed_statuses:
                raise ValueError(
                    "This claim is not currently eligible "
                    "for assessment."
                )

            # Save the assessment.
            cur.execute(
                """
                INSERT INTO assessments (
                    claim_id,
                    assessor_id,
                    damage_description,
                    estimated_repair_cost,
                    recommendation,
                    assessment_notes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING assessment_id;
                """,
                (
                    claim_id,
                    assessor_id,
                    damage_description.strip(),
                    repair_cost,
                    recommendation,
                    assessment_notes.strip() if assessment_notes else None,
                ),
            )
            result = cur.fetchone()
            assessment_id = result[0]

            # Route the claim based on the assessor's recommendation.
            if recommendation in {
                "RECOMMEND_APPROVAL",
                "RECOMMEND_REJECTION",
            }:
                new_status = "APPROVAL_PENDING"
            else:
                new_status = "UNDER_REVIEW"

            # Update the claim only when its status changes.
            if previous_status != new_status:
                cur.execute(
                    """
                    UPDATE claims
                    SET status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE claim_id = %s;
                    """,
                    (new_status, claim_id),
                )

                cur.execute(
                    """
                    INSERT INTO claim_status_history (
                        claim_id,
                        previous_status,
                        new_status,
                        changed_by,
                        change_reason
                    )
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        claim_id,
                        previous_status,
                        new_status,
                        assessor_id,
                        "Claim status updated after assessment: "
                        + recommendation,
                    ),
                )

    return assessment_id

def get_claim_assessments(claim_id):
    """Retrieve assessment history for a specific claim."""
    if not isinstance(claim_id, int) or claim_id <= 0:
        raise ValueError("Invalid claim ID.")

    query = """
        SELECT
            a.assessment_id,
            a.claim_id,
            a.damage_description,
            a.estimated_repair_cost,
            a.recommendation,
            a.assessment_notes,
            a.assessed_at,
            u.username AS assessor_username,
            u.full_name AS assessor_name
        FROM assessments AS a
        LEFT JOIN users AS u
            ON u.user_id = a.assessor_id
        WHERE a.claim_id = %s
        ORDER BY a.assessed_at DESC, a.assessment_id DESC;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (claim_id,))
            rows = cur.fetchall()

    column_names = [
        "assessment_id",
        "claim_id",
        "damage_description",
        "estimated_repair_cost",
        "recommendation",
        "assessment_notes",
        "assessed_at",
        "assessor_username",
        "assessor_name",
    ]

    return [
        dict(zip(column_names, row))
        for row in rows
    ]

def record_claim_decision(
    claim_id,
    approver_id,
    decision,
    reason,
):
    """Record an authorized approver's decision and update claim status."""

    allowed_decisions = {
        "APPROVED": "APPROVED",
        "REJECTED": "REJECTED",
        "MORE_INFORMATION_REQUIRED": "UNDER_REVIEW",
    }

    # Validate input
    if not isinstance(claim_id, int) or claim_id <= 0:
        raise ValueError("Invalid claim ID.")

    if not isinstance(approver_id, int) or approver_id <= 0:
        raise ValueError("Invalid approver ID.")

    if decision not in allowed_decisions:
        raise ValueError("Invalid claim decision.")

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("A decision reason is required.")

    if len(reason.strip()) > 5000:
        raise ValueError("Decision reason is too long.")

    new_status = allowed_decisions[decision]

    with get_db_connection() as conn:
        with conn.cursor() as cur:

            # Lock the claim row to prevent simultaneous decisions.
            cur.execute(
                """
                SELECT status
                FROM claims
                WHERE claim_id = %s
                FOR UPDATE;
                """,
                (claim_id,),
            )
            claim = cur.fetchone()

            if claim is None:
                raise ValueError("Claim not found.")

            previous_status = claim[0]

            if previous_status != "APPROVAL_PENDING":
                raise ValueError(
                    "Claim must be in APPROVAL_PENDING status "
                    "before a decision can be recorded."
                )

            # An assessment must exist before approval.
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM assessments
                    WHERE claim_id = %s
                );
                """,
                (claim_id,),
            )

            if not cur.fetchone()[0]:
                raise ValueError(
                    "An assessment is required before a decision."
                )
                        # Approval is blocked while fraud flags are unresolved.
            if decision == "APPROVED":
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM fraud_flags
                        WHERE claim_id = %s
                          AND review_status IN ('OPEN', 'UNDER_REVIEW')
                    );
                    """,
                    (claim_id,),
                )

                has_open_fraud_flags = cur.fetchone()[0]

                if has_open_fraud_flags:
                    raise ValueError(
                        "Claim approval is blocked because unresolved "
                        "fraud flags require review."
                    )

            # Record the approver's decision.
            cur.execute(
                """
                INSERT INTO claim_decisions (
                    claim_id,
                    approver_id,
                    decision,
                    reason
                )
                VALUES (%s, %s, %s, %s)
                RETURNING decision_id;
                """,
                (
                    claim_id,
                    approver_id,
                    decision,
                    reason.strip(),
                ),
            )
            decision_id = cur.fetchone()[0]

            # Update the claim's current status.
            cur.execute(
                """
                UPDATE claims
                SET status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE claim_id = %s;
                """,
                (new_status, claim_id),
            )

            # Maintain the status audit trail.
            cur.execute(
                """
                INSERT INTO claim_status_history (
                    claim_id,
                    previous_status,
                    new_status,
                    changed_by,
                    change_reason
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    claim_id,
                    previous_status,
                    new_status,
                    approver_id,
                    reason.strip(),
                ),
            )

    return decision_id

