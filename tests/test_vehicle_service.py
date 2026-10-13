
from unittest.mock import MagicMock, patch

import pytest

from services.vehicle_service import (
    get_customer_vehicles,
    register_vehicle,
)


@patch("services.vehicle_service.get_db_connection")
def test_register_vehicle_success(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db

    db.__enter__.return_value.execute.return_value.fetchone.return_value = (
        1,
        "AP 05 AB 1234",
        "Tata",
        "Nexon",
        2024,
    )

    result = register_vehicle(
        10,
        " ap 05 ab 1234 ",
        " Tata ",
        " Nexon ",
        "2024",
    )

    assert result == {
        "vehicle_id": 1,
        "registration_number": "AP 05 AB 1234",
        "make": "Tata",
        "model": "Nexon",
        "manufacturing_year": 2024,
    }

    params = (
        db.__enter__.return_value.execute.call_args.args[1]
    )
    assert params == (10, "AP 05 AB 1234", "Tata", "Nexon", 2024)


@pytest.mark.parametrize(
    ("registration", "make", "model", "year", "message"),
    [
        (" ", "Tata", "Nexon", 2024,
         "Vehicle registration number is required."),
        ("AP@123", "Tata", "Nexon", 2024,
         "Enter a valid registration number"),
        ("AP123", " ", "Nexon", 2024,
         "Vehicle manufacturer is required."),
        ("AP123", "Tata", " ", 2024,
         "Vehicle model is required."),
        ("AP123", "Tata", "Nexon", "unknown",
         "Manufacturing year must be a valid year."),
        ("AP123", "Tata", "Nexon", 1899,
         "Manufacturing year must be between 1900 and 2100."),
        ("AP123", "Tata", "Nexon", 2101,
         "Manufacturing year must be between 1900 and 2100."),
    ],
)
@patch("services.vehicle_service.get_db_connection")
def test_register_vehicle_validation(
    mock_connection, registration, make, model, year, message
):
    with pytest.raises(ValueError, match=message):
        register_vehicle(10, registration, make, model, year)

    mock_connection.assert_not_called()


@patch("services.vehicle_service.get_db_connection")
def test_register_vehicle_without_manufacturing_year(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db

    db.__enter__.return_value.execute.return_value.fetchone.return_value = (
        2,
        "AP123",
        "Honda",
        "City",
        None,
    )

    result = register_vehicle(10, "AP123", "Honda", "City", None)

    assert result["vehicle_id"] == 2
    assert result["manufacturing_year"] is None


@patch("services.vehicle_service.get_db_connection")
def test_get_customer_vehicles_returns_list(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db

    db.__enter__.return_value.execute.return_value.fetchall.return_value = [
        (2, "AP123", "Honda", "City", 2022),
        (1, "AP456", "Tata", "Nexon", 2020),
    ]

    result = get_customer_vehicles(10)

    assert result == [
        {
            "vehicle_id": 2,
            "registration_number": "AP123",
            "make": "Honda",
            "model": "City",
            "manufacturing_year": 2022,
        },
        {
            "vehicle_id": 1,
            "registration_number": "AP456",
            "make": "Tata",
            "model": "Nexon",
            "manufacturing_year": 2020,
        },
    ]

    query_params = db.__enter__.return_value.execute.call_args.args[1]
    assert query_params == (10,)


@patch("services.vehicle_service.get_db_connection")
def test_get_customer_vehicles_returns_empty_list(mock_connection):
    db = MagicMock()
    mock_connection.return_value = db
    db.__enter__.return_value.execute.return_value.fetchall.return_value = []

    assert get_customer_vehicles(10) == []
