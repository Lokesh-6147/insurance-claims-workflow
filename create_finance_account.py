
from getpass import getpass

from werkzeug.security import generate_password_hash

from db import get_db_connection


username = "lokesh.finance"
email = "lokesh.finance@example.com"
full_name = "Lokesh Finance Staff"

password = getpass("Enter a NEW test password for Finance: ")
confirm_password = getpass("Confirm the test password: ")

if not password or password != confirm_password:
    raise SystemExit("Passwords are empty or do not match.")

password_hash = generate_password_hash(password)

try:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Verify the Finance role exists.
            cur.execute(
                "SELECT role_id FROM roles WHERE role_name = %s",
                ("Finance",),
            )
            role = cur.fetchone()

            if role is None:
                raise ValueError("Finance role was not found.")

            # Prevent duplicate usernames or email addresses.
            cur.execute(
                """
                SELECT user_id
                FROM users
                WHERE username = %s OR email = %s
                """,
                (username, email),
            )

            if cur.fetchone() is not None:
                raise ValueError(
                    "The Finance username or email already exists."
                )

            # Create the active Finance staff account.
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
                RETURNING user_id
                """,
                (username, email, password_hash, full_name),
            )

            user_id = cur.fetchone()[0]

            # Assign only the Finance role.
            cur.execute(
                """
                INSERT INTO user_roles (user_id, role_id)
                VALUES (%s, %s)
                """,
                (user_id, role[0]),
            )

    print("Finance account created successfully.")
    print("Username:", username)
    print("Role: Finance")

except Exception:
    print(
        "Account creation failed. Check the error details, "
        "database connection, and duplicate account information."
    )
    raise