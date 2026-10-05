
from getpass import getpass

from werkzeug.security import generate_password_hash

from db import get_db_connection


username = "lokesh.assessor"
email = "lokesh.assessor@example.com"
full_name = "Lokesh Claims Assessor"

password = getpass("Enter a NEW test password for the assessor: ")
confirm_password = getpass("Confirm the test password: ")

if not password or password != confirm_password:
    raise SystemExit("Passwords are empty or do not match.")

password_hash = generate_password_hash(password)

try:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                    username,
                    email,
                    password_hash,
                    full_name,
                    is_active
                )
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING user_id;
                """,
                (username, email, password_hash, full_name),
            )

            user_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO user_roles (user_id, role_id)
                SELECT %s, role_id
                FROM roles
                WHERE role_name = %s
                RETURNING role_id;
                """,
                (user_id, "Claims Assessor"),
            )

            if cur.fetchone() is None:
                raise ValueError("Claims Assessor role was not found.")

    print("Claims Assessor account created successfully.")
    print(f"Username: {username}")
    print("Role: Claims Assessor")

except Exception:
    print(
        "Account creation failed. Check whether the username or "
        "email already exists, and verify the database connection."
    )
    raise