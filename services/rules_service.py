from decimal import Decimal

from db import get_db_connection


def get_active_rules():
    """Return all active configurable insurance rules."""

    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                rule_id,
                rule_code,
                rule_name,
                description,
                rule_type,
                numeric_value,
                is_active
            FROM rules
            WHERE is_active = TRUE
            ORDER BY rule_id;
            """
        ).fetchall()

    return [
        {
            "rule_id": row[0],
            "rule_code": row[1],
            "rule_name": row[2],
            "description": row[3],
            "rule_type": row[4],
            "numeric_value": Decimal(str(row[5])),
            "is_active": row[6],
        }
        for row in rows
    ]
def evaluate_amount_rule(claimed_amount, rule):
    """Evaluate whether a claim amount qualifies for the configured rule."""

    amount = Decimal(str(claimed_amount))
    limit = rule["numeric_value"]

    return amount <= limit
def has_previous_claims_in_12_months(customer_id, incident_date):
    """Check whether the customer has any claims in the previous 12 months."""

    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM claims c
            JOIN policies p
                ON c.policy_id = p.policy_id
            WHERE p.customer_id = %s
              AND c.incident_date < %s
              AND c.incident_date >= (%s - INTERVAL '12 months');
            """,
            (customer_id, incident_date, incident_date),
        ).fetchone()

    return row[0] > 0
def qualifies_for_auto_approval(
    customer_id,
    claimed_amount,
    incident_date,
    auto_approve_rule,
):
    """Check whether a claim qualifies for automatic approval."""

    amount_is_eligible = evaluate_amount_rule(
        claimed_amount,
        auto_approve_rule,
    )

    has_previous_claims = has_previous_claims_in_12_months(
        customer_id,
        incident_date,
    )

    return amount_is_eligible and not has_previous_claims
def requires_supervisor_review(claimed_amount, supervisor_rule):
    """Check whether a claim requires supervisor review."""

    amount = Decimal(str(claimed_amount))
    limit = supervisor_rule["numeric_value"]

    return amount > limit
from datetime import date


def is_early_loss(policy_start_date, incident_date, early_loss_rule):
    """Check whether a claim occurred within the configured early-loss window."""

    if incident_date < policy_start_date:
        return False

    days_since_policy_start = (incident_date - policy_start_date).days
    limit = int(early_loss_rule["numeric_value"])

    return days_since_policy_start <= limit
def count_claims_in_12_months(customer_id, incident_date):
    """Count claims for a customer during the previous 12 months."""

    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM claims c
            JOIN policies p
                ON c.policy_id = p.policy_id
            WHERE p.customer_id = %s
              AND c.incident_date <= %s
              AND c.incident_date >= (%s - INTERVAL '12 months');
            """,
            (customer_id, incident_date, incident_date),
        ).fetchone()

    return row[0]


def has_annual_claim_threshold(
    customer_id,
    incident_date,
    annual_claim_rule,
):
    """Check whether the customer reached the annual claim threshold."""

    claim_count = count_claims_in_12_months(
        customer_id,
        incident_date,
    )

    threshold = int(annual_claim_rule["numeric_value"])

    return claim_count >= threshold
def evaluate_claim_rules(
    customer_id,
    claimed_amount,
    policy_start_date,
    incident_date,
):
    """Evaluate all configurable insurance rules for a claim."""

    rules = get_active_rules()

    rules_by_code = {
        rule["rule_code"]: rule
        for rule in rules
    }

    auto_rule = rules_by_code["AUTO_APPROVE_LIMIT"]
    supervisor_rule = rules_by_code["SUPERVISOR_REVIEW_LIMIT"]
    early_loss_rule = rules_by_code["EARLY_LOSS_DAYS"]
    annual_claim_rule = rules_by_code["ANNUAL_CLAIM_COUNT"]

    auto_approval_eligible = qualifies_for_auto_approval(
        customer_id,
        claimed_amount,
        incident_date,
        auto_rule,
    )

    supervisor_review_required = requires_supervisor_review(
        claimed_amount,
        supervisor_rule,
    )

    early_loss_triggered = is_early_loss(
        policy_start_date,
        incident_date,
        early_loss_rule,
    )

    claim_count = count_claims_in_12_months(
        customer_id,
        incident_date,
    )

    annual_claim_threshold_reached = has_annual_claim_threshold(
        customer_id,
        incident_date,
        annual_claim_rule,
    )

    fraud_flags = []

    if early_loss_triggered:
        fraud_flags.append({
            "flag_type": "EARLY_LOSS",
            "description": (
                "Claim incident occurred within the configured "
                "early-loss window after policy start."
            ),
        })

    if annual_claim_threshold_reached:
        fraud_flags.append({
            "flag_type": "HIGH_CLAIM_FREQUENCY",
            "description": (
                "Customer reached the configured annual claim count threshold."
            ),
        })

    return {
        "auto_approval_eligible": auto_approval_eligible,
        "supervisor_review_required": supervisor_review_required,
        "fraud_review_required": len(fraud_flags) > 0,
        "fraud_flags": fraud_flags,
        "claim_count_12_months": claim_count,
        "evaluated_rules": {
            "AUTO_APPROVE_LIMIT": auto_approval_eligible,
            "SUPERVISOR_REVIEW_LIMIT": supervisor_review_required,
            "EARLY_LOSS_DAYS": early_loss_triggered,
            "ANNUAL_CLAIM_COUNT": annual_claim_threshold_reached,
        },
    }
def save_rule_evaluations(connection, claim_id, evaluation_result):
    """Save rule evaluation results using the caller's database transaction."""

    rules = get_active_rules()

    rules_by_code = {
        rule["rule_code"]: rule
        for rule in rules
    }

    for rule_code, triggered in evaluation_result["evaluated_rules"].items():
        rule = rules_by_code[rule_code]

        connection.execute(
            """
            INSERT INTO rule_evaluations (
                claim_id,
                rule_id,
                triggered,
                evaluation_result,
                evaluated_value
            )
            VALUES (%s, %s, %s, %s, %s);
            """,
            (
                claim_id,
                rule["rule_id"],
                triggered,
                "Rule triggered" if triggered else "Rule not triggered",
                rule["numeric_value"],
            ),
        )
def save_fraud_flags(connection, claim_id, evaluation_result):
    """Save detected fraud flags using the caller's database transaction."""

    for fraud_flag in evaluation_result["fraud_flags"]:
        connection.execute(
            """
            INSERT INTO fraud_flags (
                claim_id,
                flag_type,
                description,
                risk_level,
                review_status
            )
            VALUES (%s, %s, %s, %s, %s);
            """,
            (
                claim_id,
                fraud_flag["flag_type"],
                fraud_flag["description"],
                "HIGH",
                "OPEN",
            ),
        )
def get_claim_fraud_flags(claim_id):
    """Return all fraud flags recorded for a claim."""

    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                fraud_flag_id,
                flag_type,
                description,
                risk_level,
                review_status,
                created_at,
                reviewed_at,
                review_notes
            FROM fraud_flags
            WHERE claim_id = %s
            ORDER BY fraud_flag_id;
            """,
            (claim_id,),
        ).fetchall()

    return [
        {
            "fraud_flag_id": row[0],
            "flag_type": row[1],
            "description": row[2],
            "risk_level": row[3],
            "review_status": row[4],
            "created_at": row[5],
            "reviewed_at": row[6],
            "review_notes": row[7],
        }
        for row in rows
    ]