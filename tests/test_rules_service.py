from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from services.rules_service import (
    count_claims_in_12_months,
    evaluate_amount_rule,
    get_active_rules,
    get_claim_fraud_flags,
    has_annual_claim_threshold,
    has_previous_claims_in_12_months,
    is_early_loss,
    qualifies_for_auto_approval,
    requires_supervisor_review,
    resolve_fraud_flag,
    save_fraud_flags,
    save_rule_evaluations,
)


def test_evaluate_amount_rule_at_limit():
    rule = {"numeric_value": Decimal("50000")}
    assert evaluate_amount_rule("50000", rule) is True


def test_evaluate_amount_rule_above_limit():
    rule = {"numeric_value": Decimal("50000")}
    assert evaluate_amount_rule("50000.01", rule) is False


def test_requires_supervisor_review_above_limit():
    rule = {"numeric_value": Decimal("100000")}
    assert requires_supervisor_review("100001", rule) is True


def test_requires_supervisor_review_at_limit():
    rule = {"numeric_value": Decimal("100000")}
    assert requires_supervisor_review("100000", rule) is False


def test_is_early_loss_within_window():
    rule = {"numeric_value": Decimal("30")}
    assert is_early_loss(
        date(2026, 1, 1), date(2026, 1, 20), rule
    ) is True


def test_is_early_loss_on_last_day():
    rule = {"numeric_value": Decimal("30")}
    assert is_early_loss(
        date(2026, 1, 1), date(2026, 1, 31), rule
    ) is True


def test_is_early_loss_after_window():
    rule = {"numeric_value": Decimal("30")}
    assert is_early_loss(
        date(2026, 1, 1), date(2026, 2, 1), rule
    ) is False


def test_is_early_loss_before_policy_start():
    rule = {"numeric_value": Decimal("30")}
    assert is_early_loss(
        date(2026, 1, 10), date(2026, 1, 9), rule
    ) is False


@patch("services.rules_service.count_claims_in_12_months", return_value=3)
def test_has_annual_claim_threshold_reached(mock_count):
    rule = {"numeric_value": Decimal("3")}
    assert has_annual_claim_threshold(
        10, date(2026, 6, 1), rule
    ) is True
    mock_count.assert_called_once()


@patch("services.rules_service.count_claims_in_12_months", return_value=2)
def test_has_annual_claim_threshold_not_reached(mock_count):
    rule = {"numeric_value": Decimal("3")}
    assert has_annual_claim_threshold(
        10, date(2026, 6, 1), rule
    ) is False
@patch("services.rules_service.get_db_connection")
def test_get_active_rules_returns_records(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchall.return_value = [
        (1, "AUTO_APPROVE_LIMIT", "Auto approval", "Amount limit",
         "AMOUNT", 50000, True)
    ]

    result = get_active_rules()

    assert len(result) == 1
    assert result[0]["rule_code"] == "AUTO_APPROVE_LIMIT"
    assert result[0]["numeric_value"] == Decimal("50000")


@patch("services.rules_service.get_db_connection")
def test_get_active_rules_empty(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchall.return_value = []

    assert get_active_rules() == []


@patch("services.rules_service.get_db_connection")
def test_has_previous_claims_true(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = (1,)

    assert has_previous_claims_in_12_months(
        10, date(2026, 6, 1)
    ) is True


@patch("services.rules_service.get_db_connection")
def test_has_previous_claims_false(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = (0,)

    assert has_previous_claims_in_12_months(
        10, date(2026, 6, 1)
    ) is False


@patch("services.rules_service.has_previous_claims_in_12_months", return_value=False)
def test_qualifies_for_auto_approval(mock_previous):
    rule = {"numeric_value": Decimal("50000")}

    result = qualifies_for_auto_approval(
        10, "40000", date(2026, 6, 1), rule
    )

    assert result is True
    mock_previous.assert_called_once()


@patch("services.rules_service.has_previous_claims_in_12_months", return_value=True)
def test_auto_approval_denied_for_previous_claims(mock_previous):
    rule = {"numeric_value": Decimal("50000")}

    assert qualifies_for_auto_approval(
        10, "40000", date(2026, 6, 1), rule
    ) is False


@patch("services.rules_service.get_db_connection")
def test_count_claims_in_12_months(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = (4,)

    assert count_claims_in_12_months(
        10, date(2026, 6, 1)
    ) == 4
@patch("services.rules_service.get_active_rules")
def test_save_rule_evaluations(mock_rules):
    mock_rules.return_value = [
        {"rule_id": 1, "rule_code": "AUTO_APPROVE_LIMIT",
         "numeric_value": Decimal("50000")},
        {"rule_id": 2, "rule_code": "SUPERVISOR_REVIEW_LIMIT",
         "numeric_value": Decimal("100000")},
        {"rule_id": 3, "rule_code": "EARLY_LOSS_DAYS",
         "numeric_value": Decimal("30")},
        {"rule_id": 4, "rule_code": "ANNUAL_CLAIM_COUNT",
         "numeric_value": Decimal("3")},
    ]

    connection = MagicMock()
    result = {
        "evaluated_rules": {
            "AUTO_APPROVE_LIMIT": True,
            "SUPERVISOR_REVIEW_LIMIT": False,
            "EARLY_LOSS_DAYS": True,
            "ANNUAL_CLAIM_COUNT": False,
        }
    }

    save_rule_evaluations(connection, 100, result)

    assert connection.execute.call_count == 4


def test_save_fraud_flags():
    connection = MagicMock()
    result = {
        "fraud_flags": [
            {
                "flag_type": "EARLY_LOSS",
                "description": "Incident occurred soon after policy start.",
            },
            {
                "flag_type": "HIGH_CLAIM_FREQUENCY",
                "description": "Annual claim threshold reached.",
            },
        ]
    }

    save_fraud_flags(connection, 100, result)

    assert connection.execute.call_count == 2


@patch("services.rules_service.get_db_connection")
def test_get_claim_fraud_flags(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchall.return_value = [
        (1, "EARLY_LOSS", "Early claim", "HIGH", "OPEN",
         None, None, None)
    ]

    result = get_claim_fraud_flags(100)

    assert len(result) == 1
    assert result[0]["flag_type"] == "EARLY_LOSS"
    assert result[0]["review_status"] == "OPEN"


@pytest.mark.parametrize(
    ("flag_id", "reviewer_id", "notes", "message"),
    [
        (0, 1, "Reviewed", "Invalid fraud flag ID"),
        (1, 0, "Reviewed", "Invalid reviewer ID"),
        (1, 1, "   ", "Review notes are required"),
        (1, 1, "x" * 5001, "Review notes are too long"),
    ],
)
def test_resolve_fraud_flag_validation(
    flag_id, reviewer_id, notes, message
):
    with pytest.raises(ValueError, match=message):
        resolve_fraud_flag(flag_id, reviewer_id, notes)


@patch("services.rules_service.get_db_connection")
def test_resolve_fraud_flag_not_found(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = None

    with pytest.raises(ValueError, match="Fraud flag not found"):
        resolve_fraud_flag(1, 2, "Reviewed and verified.")


@pytest.mark.parametrize("status", ["RESOLVED", "CLOSED"])
@patch("services.rules_service.get_db_connection")
def test_resolve_fraud_flag_already_resolved(mock_connection, status):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = (
        1, status
    )

    with pytest.raises(ValueError, match="already been resolved"):
        resolve_fraud_flag(1, 2, "Reviewed and verified.")


@pytest.mark.parametrize("status", ["OPEN", "UNDER_REVIEW"])
@patch("services.rules_service.get_db_connection")
def test_resolve_fraud_flag_success(mock_connection, status):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = (
        1, status
    )

    result = resolve_fraud_flag(1, 2, "  Reviewed and verified.  ")

    assert result == 1
    assert db.__enter__.return_value.execute.call_count == 2
    update_call = db.__enter__.return_value.execute.call_args
    assert update_call.args[1] == (2, "Reviewed and verified.", 1)
