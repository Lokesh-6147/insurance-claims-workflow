from unittest.mock import MagicMock, patch

import pytest

from services.policy_service import (
    approve_policy,
    create_policy,
    get_customer_claimable_policies,
    get_customer_policies,
    get_pending_policies,
    get_policy_by_id,
    reject_policy,
)


@patch("services.policy_service.get_db_connection")
@patch("services.policy_service.secrets.token_hex", return_value="abcdef123456")
def test_create_policy_success(mock_token, mock_connection):
    db = MagicMock()
    mock_connection.return_value = db

    db.__enter__.return_value.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value=(10,))),
        MagicMock(
            fetchone=MagicMock(
                return_value=(
                    1, "POL-ABCDEF123456", 20, 10, "Full coverage",
                    15000.0, "2026-01-01", "2027-01-01", "PENDING",
                )
            )
        ),
    ]

    result = create_policy(
        20, 10, " Full coverage ", "15000",
        "2026-01-01", "2027-01-01",
    )

    assert result["policy_id"] == 1
    assert result["policy_number"] == "POL-ABCDEF123456"
    assert result["customer_id"] == 20
    assert result["vehicle_id"] == 10
    assert result["coverage_details"] == "Full coverage"
    assert result["premium_amount"] == 15000.0
    assert result["status"] == "PENDING"
    mock_token.assert_called_once_with(6)


@pytest.mark.parametrize(
    ("coverage", "premium", "start", "expiry", "message"),
    [
        (" ", "1000", "2026-01-01", "2027-01-01",
         "Coverage details are required."),
        ("Full coverage", "invalid", "2026-01-01", "2027-01-01",
         "Premium amount must be a valid number."),
        ("Full coverage", "-1", "2026-01-01", "2027-01-01",
         "Premium amount must be non-negative and valid."),
        ("Full coverage", "1000000000", "2026-01-01", "2027-01-01",
         "Premium amount must be non-negative and valid."),
        ("Full coverage", "1000", "bad-date", "2027-01-01",
         "Enter valid policy dates"),
        ("Full coverage", "1000", "2027-01-01", "2027-01-01",
         "Expiry date must be after the start date."),
        ("Full coverage", "1000", "2027-01-01", "2026-01-01",
         "Expiry date must be after the start date."),
    ],
)
@patch("services.policy_service.get_db_connection")
def test_create_policy_validation(
    mock_connection, coverage, premium, start, expiry, message
):
    with pytest.raises(ValueError, match=message):
        create_policy(20, 10, coverage, premium, start, expiry)

    mock_connection.assert_not_called()


@patch("services.policy_service.get_db_connection")
def test_create_policy_rejects_vehicle_not_owned_by_customer(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = None

    with pytest.raises(ValueError, match="does not belong to your account"):
        create_policy(
            20, 999, "Full coverage", 1000,
            "2026-01-01", "2027-01-01",
        )

    assert db.__enter__.return_value.execute.call_count == 1
@patch("services.policy_service.get_db_connection")
def test_get_customer_policies_returns_records(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchall.return_value = [
        (1, "POL-ONE", 20, 10, "Full coverage", 15000.0,
         "2026-01-01", "2027-01-01", "ACTIVE", "Car", "ABC123")
    ]

    result = get_customer_policies(20)

    assert len(result) == 1
    assert result[0]["policy_number"] == "POL-ONE"


@patch("services.policy_service.get_db_connection")
def test_get_customer_policies_empty(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchall.return_value = []

    assert get_customer_policies(20) == []


@patch("services.policy_service.get_db_connection")
def test_get_pending_policies_returns_records(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchall.return_value = [
        (1, "POL-ONE", 20, 10, "Full coverage", 15000.0,
         "2026-01-01", "2027-01-01", "PENDING",
         "Lokesh", "lokesh@example.com", "Car", "ABC123", "Honda", "City")
    ]

    result = get_pending_policies()

    assert len(result) == 1
    assert result[0]["policy_number"] == "POL-ONE"


@patch("services.policy_service.get_db_connection")
def test_get_pending_policies_empty(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchall.return_value = []

    assert get_pending_policies() == []


@patch("services.policy_service.get_db_connection")
def test_get_policy_by_id_found(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = (
        1, "POL-ONE", 20, 10, "Full coverage", 15000.0,
        "2026-01-01", "2027-01-01", "ACTIVE",
        "Lokesh", "lokesh@example.com", "Car", "ABC123", "Honda", "City"
    )

    result = get_policy_by_id(1)

    assert result is not None
    assert result["policy_number"] == "POL-ONE"


@patch("services.policy_service.get_db_connection")
def test_get_policy_by_id_not_found(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = None

    assert get_policy_by_id(999) is None
@patch("services.policy_service.get_db_connection")
def test_approve_policy_success(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    connection = db.__enter__.return_value
    connection.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value=(1, "POL-ONE", "PENDING"))),
        MagicMock(fetchone=MagicMock(return_value=(
            1, "POL-ONE", 20, 10, "Full coverage", 15000.0,
            "2026-01-01", "2027-01-01", "ACTIVE"
        ))),
    ]

    result = approve_policy(1)

    assert result["policy_number"] == "POL-ONE"
    assert result["status"] == "ACTIVE"


@patch("services.policy_service.get_db_connection")
def test_approve_policy_not_found(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = None

    with pytest.raises(ValueError, match="Policy not found"):
        approve_policy(999)


@patch("services.policy_service.get_db_connection")
def test_approve_policy_not_pending(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = (
        1, "POL-ONE", 20, 10, "Full coverage", 15000.0,
        "2026-01-01", "2027-01-01", "ACTIVE"
    )

    with pytest.raises(ValueError):
        approve_policy(1)


@patch("services.policy_service.get_db_connection")
def test_reject_policy_success(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    connection = db.__enter__.return_value
    connection.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value=(1, "POL-ONE", "PENDING"))),
        MagicMock(fetchone=MagicMock(return_value=(
            1, "POL-ONE", 20, 10, "Full coverage", 15000.0,
            "2026-01-01", "2027-01-01", "REJECTED"
        ))),
    ]

    result = reject_policy(1)

    assert result["policy_number"] == "POL-ONE"
    assert result["status"] == "REJECTED"


@patch("services.policy_service.get_db_connection")
def test_reject_policy_not_found(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = None

    with pytest.raises(ValueError, match="Policy not found"):
        reject_policy(999)


@patch("services.policy_service.get_db_connection")
def test_reject_policy_not_pending(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = (
        1, "POL-ONE", 20, 10, "Full coverage", 15000.0,
        "2026-01-01", "2027-01-01", "REJECTED"
    )

    with pytest.raises(ValueError):
        reject_policy(1)


@patch("services.policy_service.get_db_connection")
def test_get_customer_claimable_policies_returns_records(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchall.return_value = [
        (1, "POL-ONE", 10, "Full coverage", 15000.0,
         "2026-01-01", "2027-01-01", "ACTIVE")
    ]

    result = get_customer_claimable_policies(20)

    assert len(result) == 1
    assert result[0]["policy_number"] == "POL-ONE"


@patch("services.policy_service.get_db_connection")
def test_get_customer_claimable_policies_empty(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchall.return_value = []

    assert get_customer_claimable_policies(20) == []
