
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.security import check_password_hash

from services.customer_service import register_customer


@patch("services.customer_service.get_db_connection")
def test_register_customer_success(mock_connection):
    # Mock the database connections and transaction.
    first_db = MagicMock()
    second_db = MagicMock()
    mock_connection.side_effect = [first_db, second_db]

    # No customer with this email already exists.
    first_db.__enter__.return_value.execute.return_value.fetchone.return_value = None

    # Simulate the inserted customer returned by PostgreSQL.
    second_db.__enter__.return_value.execute.return_value.fetchone.return_value = (
        1,
        "ACC-ABC123",
        "Lokesh",
        "lokesh@example.com",
    )

    result = register_customer(
        "  Lokesh  ",
        "  LOKESH@EXAMPLE.COM ",
        "9876543210",
        "SecurePass123",
    )

    assert result == {
        "customer_id": 1,
        "account_id": "ACC-ABC123",
        "full_name": "Lokesh",
        "email": "lokesh@example.com",
    }
    assert mock_connection.call_count == 2

    # The stored password must be hashed, not plain text.
    insert_calls = second_db.__enter__.return_value.execute.call_args_list
    password_insert = insert_calls[1]
    stored_hash = password_insert.args[1][1]
    assert stored_hash != "SecurePass123"
    assert check_password_hash(stored_hash, "SecurePass123")


@pytest.mark.parametrize(
    ("full_name", "email", "phone", "password", "message"),
    [
        ("   ", "lokesh@example.com", "9876543210", "SecurePass123",
         "Full name is required."),
        ("Lokesh", "invalid-email", "9876543210", "SecurePass123",
         "Enter a valid email address."),
        ("Lokesh", "lokesh@example.com", "12345", "SecurePass123",
         "Phone number must contain exactly 10 digits."),
        ("Lokesh", "lokesh@example.com", "9876543210", "short",
         "Password must contain at least 8 characters."),
    ],
)
@patch("services.customer_service.get_db_connection")
def test_register_customer_validation(
    mock_connection, full_name, email, phone, password, message
):
    with pytest.raises(ValueError, match=message):
        register_customer(full_name, email, phone, password)

    # Invalid input must be rejected before accessing the database.
    mock_connection.assert_not_called()


@patch("services.customer_service.get_db_connection")
def test_register_customer_duplicate_email(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchone.return_value = (1,)

    with pytest.raises(
        ValueError, match="An account with this email already exists."
    ):
        register_customer(
            "Lokesh",
            "lokesh@example.com",
            "9876543210",
            "SecurePass123",
        )

    # Only the duplicate-email lookup should happen.
    assert db.__enter__.return_value.execute.call_count == 1
