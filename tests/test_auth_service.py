from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from services.auth_service import (
    authenticate_customer,
    authenticate_staff,
    get_current_staff_roles,
)


@patch("services.auth_service.get_db_connection")
def test_authenticate_customer_success(mock_connection):
    mock_conn = MagicMock()
    mock_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = (
        1, "ACC-001", "Test Customer", "customer@example.com",
        generate_password_hash("CustomerPass123!"), True,
    )

    result = authenticate_customer(
        " CUSTOMER@example.com ", "CustomerPass123!"
    )

    assert result == {
        "customer_id": 1,
        "account_id": "ACC-001",
        "full_name": "Test Customer",
        "email": "customer@example.com",
    }
    assert mock_conn.execute.call_args.args[1] == ("customer@example.com",)


@patch("services.auth_service.get_db_connection")
def test_authenticate_customer_unknown_email(mock_connection):
    mock_conn = MagicMock()
    mock_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = None

    assert authenticate_customer("missing@example.com", "AnyPassword") is None


@patch("services.auth_service.get_db_connection")
def test_authenticate_customer_inactive_account(mock_connection):
    mock_conn = MagicMock()
    mock_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = (
        1, "ACC-001", "Test Customer", "customer@example.com",
        generate_password_hash("CustomerPass123!"), False,
    )

    assert authenticate_customer("customer@example.com", "CustomerPass123!") is None


@patch("services.auth_service.get_db_connection")
def test_authenticate_customer_wrong_password(mock_connection):
    mock_conn = MagicMock()
    mock_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = (
        1, "ACC-001", "Test Customer", "customer@example.com",
        generate_password_hash("CustomerPass123!"), True,
    )

    assert authenticate_customer("customer@example.com", "WrongPassword") is None


@patch("services.auth_service.get_db_connection")
def test_authenticate_staff_success(mock_connection):
    mock_conn = MagicMock()
    mock_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = (
        7, "test.staff", "staff@example.com", "Test Staff",
        generate_password_hash("StaffPass123!"), True,
        ["Claims Approver", "Finance"],
    )

    result = authenticate_staff("test.staff", "StaffPass123!")

    assert result == {
        "user_id": 7,
        "username": "test.staff",
        "email": "staff@example.com",
        "full_name": "Test Staff",
        "roles": ["Claims Approver", "Finance"],
    }


@patch("services.auth_service.get_db_connection")
def test_authenticate_staff_unknown_user(mock_connection):
    mock_conn = MagicMock()
    mock_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = None

    assert authenticate_staff("missing.staff", "AnyPassword") is None


@patch("services.auth_service.get_db_connection")
def test_authenticate_staff_inactive_user(mock_connection):
    mock_conn = MagicMock()
    mock_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = (
        7, "test.staff", "staff@example.com", "Test Staff",
        generate_password_hash("StaffPass123!"), False, ["Finance"],
    )

    assert authenticate_staff("test.staff", "StaffPass123!") is None


@patch("services.auth_service.get_db_connection")
def test_authenticate_staff_without_roles(mock_connection):
    mock_conn = MagicMock()
    mock_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = (
        7, "test.staff", "staff@example.com", "Test Staff",
        generate_password_hash("StaffPass123!"), True, [],
    )

    assert authenticate_staff("test.staff", "StaffPass123!") is None


@patch("services.auth_service.get_db_connection")
def test_authenticate_staff_wrong_password(mock_connection):
    mock_conn = MagicMock()
    mock_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = (
        7, "test.staff", "staff@example.com", "Test Staff",
        generate_password_hash("StaffPass123!"), True, ["Finance"],
    )

    assert authenticate_staff("test.staff", "WrongPassword") is None


@patch("services.auth_service.get_db_connection")
def test_get_current_staff_roles_returns_roles(mock_connection):
    mock_conn = MagicMock()
    mock_connection.return_value.__enter__.return_value = mock_conn
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [
        ("Claims Approver",),
        ("Finance",),
    ]

    result = get_current_staff_roles(7)

    assert result == ["Claims Approver", "Finance"]
    mock_cursor.execute.assert_called_once()
    assert mock_cursor.execute.call_args.args[1] == (7,)


def test_get_current_staff_roles_rejects_invalid_ids():
    assert get_current_staff_roles(0) == []
    assert get_current_staff_roles(-1) == []
    assert get_current_staff_roles("7") == []
    assert get_current_staff_roles(None) == []
