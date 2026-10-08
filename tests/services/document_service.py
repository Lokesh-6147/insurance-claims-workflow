
import os
from uuid import uuid4

from werkzeug.utils import secure_filename

from db import get_db_connection


ALLOWED_FILE_TYPES = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
}

ALLOWED_DOCUMENT_TYPES = {
    "ACCIDENT_PHOTO",
    "REPAIR_ESTIMATE",
    "POLICE_REPORT",
    "OTHER",
}


def upload_claim_document(
    customer_id,
    claim_id,
    document_type,
    uploaded_file,
    upload_folder,
):
    """Validate, store, and register a claim document."""

    if not uploaded_file or not uploaded_file.filename:
        raise ValueError("Please select a file to upload.")

    document_type = (document_type or "").strip().upper()

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError("Please select a valid document type.")

    original_filename = secure_filename(uploaded_file.filename)

    if not original_filename:
        raise ValueError("The filename is invalid.")

    extension = os.path.splitext(original_filename)[1].lower()

    if extension not in ALLOWED_FILE_TYPES:
        raise ValueError("Only PDF, JPG, JPEG, and PNG files are allowed.")

    expected_mime, expected_signature = ALLOWED_FILE_TYPES[extension]

    if uploaded_file.mimetype != expected_mime:
        raise ValueError("The file type does not match its extension.")

    # Check the file signature instead of trusting the filename alone.
    uploaded_file.stream.seek(0)
    signature = uploaded_file.stream.read(len(expected_signature))
    uploaded_file.stream.seek(0)

    if signature != expected_signature:
        raise ValueError("The uploaded file content is invalid.")

    os.makedirs(upload_folder, exist_ok=True)

    # Generate a random filename to avoid collisions and unsafe paths.
    stored_filename = f"{uuid4().hex}{extension}"
    file_path = os.path.join(upload_folder, stored_filename)

    # Store a relative reference in the database, not a public URL.
    file_reference = os.path.join("claims", stored_filename).replace(
        os.sep, "/"
    )

    try:
        with get_db_connection() as connection:
            claim = connection.execute(
                """
                SELECT c.claim_id
                FROM claims AS c
                JOIN policies AS p
                    ON c.policy_id = p.policy_id
                WHERE c.claim_id = %s
                  AND p.customer_id = %s
                """,
                (claim_id, customer_id),
            ).fetchone()

            if claim is None:
                raise ValueError(
                    "Claim not found or you do not have access to it."
                )

            # Save the file only after confirming claim ownership.
            uploaded_file.save(file_path)

            connection.execute(
                """
                INSERT INTO claim_documents (
                    claim_id,
                    document_type,
                    file_reference
                )
                VALUES (%s, %s, %s)
                """,
                (claim_id, document_type, file_reference),
            )

    except Exception:
        # Avoid leaving an orphaned file if database registration fails.
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    return {
        "claim_id": claim_id,
        "document_type": document_type,
        "file_reference": file_reference,
        "verification_status": "PENDING",
    }

def get_claim_documents(customer_id, claim_id):
    """Return documents for a claim owned by the specified customer."""

    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                d.document_id,
                d.document_type,
                d.verification_status,
                d.uploaded_at
            FROM claim_documents AS d
            JOIN claims AS c
                ON d.claim_id = c.claim_id
            JOIN policies AS p
                ON c.policy_id = p.policy_id
            WHERE p.customer_id = %s
              AND c.claim_id = %s
            ORDER BY d.uploaded_at DESC
            """,
            (customer_id, claim_id),
        ).fetchall()

    return [
        {
            "document_id": row[0],
            "document_type": row[1],
            "verification_status": row[2],
            "uploaded_at": row[3],
        }
        for row in rows
    ]

def get_staff_claim_documents(claim_id):
    """Return document metadata for a claim viewed by authorized staff."""
    if not isinstance(claim_id, int) or claim_id <= 0:
        return []

    query = """
        SELECT
            document_id,
            document_type,
            verification_status,
            review_notes,
            uploaded_at,
            reviewed_at,
            reviewed_by
        FROM claim_documents
        WHERE claim_id = %s
        ORDER BY uploaded_at DESC;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (claim_id,))
            rows = cur.fetchall()
            columns = [column.name for column in cur.description]

    return [dict(zip(columns, row)) for row in rows]

def review_claim_document(
    document_id,
    reviewer_id,
    verification_status,
    review_notes=None,
):
    """Record a staff member's document review."""
    allowed_statuses = {
        "VERIFIED",
        "REJECTED",
        "RESUBMISSION_REQUIRED",
    }

    if not isinstance(document_id, int) or document_id <= 0:
        raise ValueError("Invalid document ID.")

    if not isinstance(reviewer_id, int) or reviewer_id <= 0:
        raise ValueError("Invalid reviewer ID.")

    if verification_status not in allowed_statuses:
        raise ValueError("Invalid document verification status.")

    if review_notes is not None and not isinstance(review_notes, str):
        raise ValueError("Review notes must be text.")

    query = """
        UPDATE claim_documents
        SET
            verification_status = %s,
            reviewed_by = %s,
            review_notes = %s,
            reviewed_at = CURRENT_TIMESTAMP
        WHERE document_id = %s
        RETURNING document_id;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    verification_status,
                    reviewer_id,
                    review_notes,
                    document_id,
                ),
            )
            updated_document = cur.fetchone()

            if updated_document is None:
                raise ValueError("Document not found.")

    return updated_document[0]