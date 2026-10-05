from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import psycopg
import pytest

from services.settlement_service import create_settlement, process_payment

@patch("services.settlement_service.get_db_connection")
def test_process_payment_success(mock_get_connection):
    # Prepare a fake database connection.
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Simulate a pending settlement and a claim awaiting payment.
    mock_cursor.fetchone.return_value = (
        1,          # claim_id
        "PENDING",  # payment_status
        "SETTLEMENT_PENDING",
    )

    mock_cursor.rowcount = 1

    settlement_id = process_payment(
        settlement_id=99,
        payment_reference="TEST-PAYMENT-001",
        payment_method="UPI",
        processed_by=4,
    )

    assert settlement_id == 99

    # Confirm that the payment was recorded as paid.
    update_calls = [
        call.args[0]
        for call in mock_cursor.execute.call_args_list
        if "UPDATE settlements" in call.args[0]
    ]

    assert len(update_calls) == 1
    assert "payment_status = 'PAID'" in update_calls[0]

    # Confirm the claim status was updated.
    claim_update_calls = [
        call.args[0]
        for call in mock_cursor.execute.call_args_list
        if "UPDATE claims" in call.args[0]
    ]

    assert len(claim_update_calls) == 1
    assert "status = 'SETTLED'" in claim_update_calls[0]


def test_process_payment_rejects_invalid_settlement_id():
    with pytest.raises(ValueError, match="valid settlement ID"):
        process_payment(
            settlement_id=0,
            payment_reference="TEST-001",
            payment_method="UPI",
        )


def test_process_payment_rejects_invalid_payment_method():
    with pytest.raises(ValueError, match="Payment method"):
        process_payment(
            settlement_id=99,
            payment_reference="TEST-001",
            payment_method="CASH",
        )


def test_process_payment_rejects_empty_reference():
    with pytest.raises(ValueError, match="Payment reference"):
        process_payment(
            settlement_id=99,
            payment_reference="   ",
            payment_method="UPI",
        )

@patch("services.settlement_service.get_db_connection")
def test_process_payment_rejects_already_paid_settlement(
    mock_get_connection,
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Simulate a settlement that has already been paid.
    mock_cursor.fetchone.return_value = (
        1,          # claim_id
        "PAID",     # payment_status
        "SETTLED",  # claim_status
    )

    with pytest.raises(
        ValueError,
        match="Only pending settlements can be paid",
    ):
        process_payment(
            settlement_id=99,
            payment_reference="TEST-PAYMENT-002",
            payment_method="UPI",
            processed_by=4,
        )

    # No database UPDATE should occur for an already-paid settlement.
    update_calls = [
        call.args[0]
        for call in mock_cursor.execute.call_args_list
        if call.args and call.args[0].strip().upper().startswith("UPDATE")
    ]

    assert update_calls == []
    

@patch("services.settlement_service.get_db_connection")
def test_process_payment_rolls_back_when_claim_update_fails(
    mock_get_connection,
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchone.return_value = (
        1,
        "PENDING",
        "SETTLEMENT_PENDING",
    )

    def execute_side_effect(sql, params=None):
        if "UPDATE settlements" in sql:
            mock_cursor.rowcount = 1
        elif "UPDATE claims" in sql:
            mock_cursor.rowcount = 0

    mock_cursor.execute.side_effect = execute_side_effect

    # Simulate Psycopg rolling back when an exception leaves
    # the connection context manager.
    def connection_exit(exc_type, exc_value, traceback):
        if exc_type is not None:
            mock_conn.rollback()
        else:
            mock_conn.commit()
        return False

    mock_get_connection.return_value.__exit__.side_effect = (
        connection_exit
    )

    with pytest.raises(
        ValueError,
        match="Claim status could not be updated",
    ):
        process_payment(
            settlement_id=99,
            payment_reference="TEST-ROLLBACK-001",
            payment_method="UPI",
            processed_by=4,
        )

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
    
@patch("services.settlement_service.get_db_connection")
def test_create_settlement_handles_duplicate_constraint(
    mock_get_connection,
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Simulate a PostgreSQL unique-constraint error with its
    # constraint name available, as it would be for a DB error.
    class DuplicateClaimSettlement(psycopg.errors.UniqueViolation):
        @property
        def diag(self):
            return SimpleNamespace(
                constraint_name="settlements_claim_id_key"
            )

    def execute_side_effect(sql, params=None):
        if "SELECT status" in sql:
            mock_cursor.fetchone.return_value = ("APPROVED",)
        elif "SELECT settlement_id" in sql:
            mock_cursor.fetchone.return_value = None
        elif "INSERT INTO settlements" in sql:
            raise DuplicateClaimSettlement("Duplicate claim settlement")

    mock_cursor.execute.side_effect = execute_side_effect

    with pytest.raises(
        ValueError,
        match="A settlement already exists for this claim",
    ):
        create_settlement(
            claim_id=99,
            approved_amount="500.00",
            created_by=3,
        )

    # Ensure the duplicate insert was attempted.
    insert_calls = [
        c for c in mock_cursor.execute.call_args_list
        if "INSERT INTO settlements" in c.args[0]
    ]
    assert len(insert_calls) == 1
    
def test_create_settlement_rejects_invalid_claim_id():
    with pytest.raises(ValueError, match="valid claim ID"):
        create_settlement(
            claim_id=0,
            approved_amount="500.00",
        )


def test_create_settlement_rejects_invalid_amount():
    with pytest.raises(ValueError, match="greater than zero"):
        create_settlement(
            claim_id=99,
            approved_amount="0",
        )


@patch("services.settlement_service.get_db_connection")
def test_create_settlement_rejects_missing_claim(
    mock_get_connection,
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # The database returns no claim.
    mock_cursor.fetchone.return_value = None

    with pytest.raises(ValueError, match="Claim not found"):
        create_settlement(
            claim_id=999,
            approved_amount="500.00",
        )

    # No settlement insert should be attempted.
    insert_calls = [
        c for c in mock_cursor.execute.call_args_list
        if "INSERT INTO settlements" in c.args[0]
    ]
    assert insert_calls == []


@patch("services.settlement_service.get_db_connection")
def test_process_payment_rejects_missing_settlement(
    mock_get_connection,
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # The database returns no matching settlement.
    mock_cursor.fetchone.return_value = None

    with pytest.raises(ValueError, match="Settlement not found"):
        process_payment(
            settlement_id=999,
            payment_reference="TEST-MISSING-001",
            payment_method="UPI",
        )

    # No payment or claim update should occur.
    update_calls = [
        c for c in mock_cursor.execute.call_args_list
        if c.args[0].strip().upper().startswith("UPDATE")
    ]
    assert update_calls == []
    
@patch("services.settlement_service.get_db_connection")
def test_create_settlement_rejects_unapproved_claim(
    mock_get_connection,
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # The claim exists but has not been approved.
    mock_cursor.fetchone.return_value = ("SUBMITTED",)

    def execute_side_effect(sql, params=None):
        if "SELECT status" in sql:
            mock_cursor.fetchone.return_value = ("SUBMITTED",)
        elif "SELECT settlement_id" in sql:
            mock_cursor.fetchone.return_value = None

    mock_cursor.execute.side_effect = execute_side_effect

    with pytest.raises(
        ValueError,
        match="Only approved claims can be settled",
    ):
        create_settlement(
            claim_id=999,
            approved_amount="500.00",
        )

    # A settlement must not be inserted for an unapproved claim.
    insert_calls = [
        c for c in mock_cursor.execute.call_args_list
        if "INSERT INTO settlements" in c.args[0]
    ]
    assert insert_calls == []