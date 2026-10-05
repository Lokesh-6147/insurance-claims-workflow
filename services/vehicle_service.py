
import re

from db import get_db_connection


def register_vehicle(
    customer_id,
    registration_number,
    make,
    model,
    manufacturing_year,
):
    """Register a vehicle for the authenticated customer."""

    registration_number = registration_number.strip().upper()
    make = make.strip()
    model = model.strip()

    if not registration_number:
        raise ValueError("Vehicle registration number is required.")

    if not re.fullmatch(r"[A-Z0-9 -]{1,20}", registration_number):
        raise ValueError(
            "Enter a valid registration number using letters, digits, "
            "spaces or hyphens."
        )

    if not make:
        raise ValueError("Vehicle manufacturer is required.")

    if not model:
        raise ValueError("Vehicle model is required.")

    if manufacturing_year is not None:
        try:
            manufacturing_year = int(manufacturing_year)
        except (TypeError, ValueError):
            raise ValueError("Manufacturing year must be a valid year.")

        if not 1900 <= manufacturing_year <= 2100:
            raise ValueError(
                "Manufacturing year must be between 1900 and 2100."
            )

    with get_db_connection() as connection:
        with connection.transaction():
            vehicle = connection.execute(
                """
                INSERT INTO vehicles (
                    customer_id,
                    registration_number,
                    make,
                    model,
                    manufacturing_year
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING
                    vehicle_id,
                    registration_number,
                    make,
                    model,
                    manufacturing_year
                """,
                (
                    customer_id,
                    registration_number,
                    make,
                    model,
                    manufacturing_year,
                ),
            ).fetchone()

    return {
        "vehicle_id": vehicle[0],
        "registration_number": vehicle[1],
        "make": vehicle[2],
        "model": vehicle[3],
        "manufacturing_year": vehicle[4],
    }

def get_customer_vehicles(customer_id):
    """Return all vehicles registered by a specific customer."""

    with get_db_connection() as connection:
        vehicles = connection.execute(
            """
            SELECT
                vehicle_id,
                registration_number,
                make,
                model,
                manufacturing_year
            FROM vehicles
            WHERE customer_id = %s
            ORDER BY vehicle_id DESC
            """,
            (customer_id,),
        ).fetchall()

    return [
        {
            "vehicle_id": vehicle[0],
            "registration_number": vehicle[1],
            "make": vehicle[2],
            "model": vehicle[3],
            "manufacturing_year": vehicle[4],
        }
        for vehicle in vehicles
    ]