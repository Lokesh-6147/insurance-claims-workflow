
import re
import secrets

from werkzeug.security import generate_password_hash

from db import get_db_connection


def register_customer(full_name, email, phone, password):
    """Create a customer profile and its login account."""

    # 1. Validate and normalize the submitted information.
    full_name = full_name.strip()
    email = email.strip().lower()
    phone = phone.strip()

    if not full_name:
        raise ValueError("Full name is required.")

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter a valid email address.")

    if not re.fullmatch(r"\d{10}", phone):
        raise ValueError("Phone number must contain exactly 10 digits.")

    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    # 2. Hash the password. Never store the original password.
    password_hash = generate_password_hash(password)

    # 3. Generate a unique customer account identifier.
    account_id = f"ACC-{secrets.token_hex(6).upper()}"
    
    # Check whether a customer already registered with this email.
    with get_db_connection() as connection:
        existing_customer = connection.execute(
            "SELECT 1 FROM customers WHERE email = %s",
            (email,),
        ).fetchone()

    if existing_customer:
        raise ValueError("An account with this email already exists.")

    # 4. Create the customer and login account together.
    with get_db_connection() as connection:
        with connection.transaction():
            customer = connection.execute(
                """
                INSERT INTO customers
                    (account_id, full_name, email, phone)
                VALUES (%s, %s, %s, %s)
                RETURNING customer_id, account_id, full_name, email
                """,
                (account_id, full_name, email, phone),
            ).fetchone()

            connection.execute(
                """
                INSERT INTO customer_accounts (customer_id, password_hash)
                VALUES (%s, %s)
                """,
                (customer[0], password_hash),
            )

    return {
        "customer_id": customer[0],
        "account_id": customer[1],
        "full_name": customer[2],
        "email": customer[3],
    }