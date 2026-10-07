from unittest.mock import MagicMock, patch

import pytest

from services.claim_service import record_claim_decision


@patch("services.claim_service.get_db_connection")
def test_approval_is_blocked_when_fraud_flags_are_unresolved(
    mock_get_connection,
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    def execute_side_effect(sql, params=None):
        if "SELECT status" in sql:
            mock_cursor.fetchone.return_value = ("APPROVAL_PENDING",)

        elif "SELECT EXISTS" in sql and "assessments" in sql:
            mock_cursor.fetchone.return_value = (True,)

        elif "SELECT EXISTS" in sql and "fraud_flags" in sql:
            mock_cursor.fetchone.return_value = (True,)

    mock_cursor.execute.side_effect = execute_side_effect

    with pytest.raises(
        ValueError,
        match="unresolved fraud flags require review",
    ):
        record_claim_decision(
            claim_id=99,
            approver_id=3,
            decision="APPROVED",
            reason="Approve claim",
        )

    # Approval must not be recorded.
    decision_inserts = [
        call
        for call in mock_cursor.execute.call_args_list
        if "INSERT INTO claim_decisions" in call.args[0]
    ]

    assert decision_inserts == []

    # Claim status must not be updated.
    claim_updates = [
        call
        for call in mock_cursor.execute.call_args_list
        if "UPDATE claims" in call.args[0]
    ]

    assert claim_updates == []
@patch("services.claim_service.get_db_connection")
def test_approval_is_allowed_when_no_unresolved_fraud_flags(
    mock_get_connection,
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    def execute_side_effect(sql, params=None):
        if "SELECT status" in sql:
            mock_cursor.fetchone.return_value = ("APPROVAL_PENDING",)

        elif "SELECT EXISTS" in sql and "assessments" in sql:
            mock_cursor.fetchone.return_value = (True,)

        elif "SELECT EXISTS" in sql and "fraud_flags" in sql:
            mock_cursor.fetchone.return_value = (False,)

        elif "INSERT INTO claim_decisions" in sql:
            mock_cursor.fetchone.return_value = (123,)

    mock_cursor.execute.side_effect = execute_side_effect

    decision_id = record_claim_decision(
        claim_id=99,
        approver_id=3,
        decision="APPROVED",
        reason="Claim reviewed and approved.",
    )

    assert decision_id == 123

    # Confirm that the decision was recorded.
    decision_inserts = [
        call
        for call in mock_cursor.execute.call_args_list
        if "INSERT INTO claim_decisions" in call.args[0]
    ]

    assert len(decision_inserts) == 1

    # Confirm that the claim was moved to APPROVED.
    claim_updates = [
        call
        for call in mock_cursor.execute.call_args_list
        if "UPDATE claims" in call.args[0]
    ]

    assert len(claim_updates) == 1
    assert "SET status = %s" in claim_updates[0].args[0]