
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db_connection


def authenticate_customer(email, password):
    """Verify a customer's email and password."""

    email = email.strip().lower()

    with get_db_connection() as connection:
        customer = connection.execute(
            """
            SELECT
                c.customer_id,
                c.account_id,
                c.full_name,
                c.email,
                ca.password_hash,
                ca.is_active
            FROM customers AS c
            JOIN customer_accounts AS ca
                ON ca.customer_id = c.customer_id
            WHERE c.email = %s
            """,
            (email,),
        ).fetchone()

    # Reject unknown emails and inactive accounts.
    if customer is None or not customer[5]:
        return None

    # Compare the submitted password with the stored password hash.
    if not check_password_hash(customer[4], password):
        return None

    return {
        "customer_id": customer[0],
        "account_id": customer[1],
        "full_name": customer[2],
        "email": customer[3],
    }

def authenticate_staff(username, password):
    """Verify staff credentials and retrieve their assigned roles."""

    username = username.strip()

    with get_db_connection() as connection:
        staff = connection.execute(
            """
            SELECT
                u.user_id,
                u.username,
                u.email,
                u.full_name,
                u.password_hash,
                u.is_active,
                COALESCE(
                    ARRAY_AGG(r.role_name)
                    FILTER (WHERE r.role_name IS NOT NULL),
                    ARRAY[]::VARCHAR[]
                ) AS roles
            FROM users AS u
            LEFT JOIN user_roles AS ur
                ON ur.user_id = u.user_id
            LEFT JOIN roles AS r
                ON r.role_id = ur.role_id
            WHERE u.username = %s
            GROUP BY
                u.user_id,
                u.username,
                u.email,
                u.full_name,
                u.password_hash,
                u.is_active
            """,
            (username,),
        ).fetchone()

    # Reject unknown, inactive, or role-less accounts.
    if staff is None or not staff[5] or not staff[6]:
        return None

    if not check_password_hash(staff[4], password):
        return None

    return {
        "user_id": staff[0],
        "username": staff[1],
        "email": staff[2],
        "full_name": staff[3],
        "roles": list(staff[6]),
    }

def get_current_staff_roles(user_id):
    """Fetch the staff member's currently assigned roles."""
    if not isinstance(user_id, int) or user_id <= 0:
        return []

    query = """
        SELECT r.role_name
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.user_id
        JOIN roles r ON r.role_id = ur.role_id
        WHERE u.user_id = %s
          AND u.is_active = TRUE
        ORDER BY r.role_name;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()

    return [row[0] for row in rows]