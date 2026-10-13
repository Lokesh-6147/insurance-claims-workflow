
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.datastructures import FileStorage

from services.document_service import (
    get_claim_documents,
    get_staff_claim_documents,
    review_claim_document,
    upload_claim_document,
)


def make_upload(filename="accident.pdf", content=b"%PDF-1.7 test content",
                mimetype="application/pdf"):
    return FileStorage(
        stream=BytesIO(content),
        filename=filename,
        content_type=mimetype,
    )


@patch("services.document_service.get_db_connection")
def test_upload_claim_document_success(mock_connection, tmp_path):
    db = MagicMock()
    mock_connection.return_value.__enter__.return_value = db
    db.execute.return_value.fetchone.return_value = (101,)

    result = upload_claim_document(
        10, 101, " accident_photo ", make_upload(), str(tmp_path)
    )

    assert result["claim_id"] == 101
    assert result["document_type"] == "ACCIDENT_PHOTO"
    assert result["verification_status"] == "PENDING"
    assert result["file_reference"].startswith("claims/")
    assert (tmp_path / result["file_reference"].split("/")[-1]).exists()
    assert db.execute.call_count == 2


@pytest.mark.parametrize(
    ("uploaded_file", "document_type", "message"),
    [
        (None, "ACCIDENT_PHOTO", "Please select a file to upload."),
        (make_upload(), "INVALID", "Please select a valid document type."),
        (make_upload(filename="!!!"), "ACCIDENT_PHOTO",
         "The filename is invalid."),
        (make_upload(filename="notes.txt"), "ACCIDENT_PHOTO",
         "Only PDF, JPG, JPEG, and PNG files are allowed."),
        (make_upload(mimetype="text/plain"), "ACCIDENT_PHOTO",
         "The file type does not match its extension."),
        (make_upload(content=b"not a PDF"), "ACCIDENT_PHOTO",
         "The uploaded file content is invalid."),
    ],
)
def test_upload_claim_document_validation(
    uploaded_file, document_type, message, tmp_path
):
    with patch("services.document_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match=message):
            upload_claim_document(
                10, 101, document_type, uploaded_file, str(tmp_path)
            )

        mock_db.assert_not_called()


@patch("services.document_service.get_db_connection")
def test_upload_rejects_claim_not_owned_by_customer(
    mock_connection, tmp_path
):
    db = MagicMock()
    mock_connection.return_value.__enter__.return_value = db
    db.execute.return_value.fetchone.return_value = None
    uploaded_file = make_upload()

    with pytest.raises(ValueError, match="Claim not found"):
        upload_claim_document(
            10, 101, "ACCIDENT_PHOTO", uploaded_file, str(tmp_path)
        )

    assert list(tmp_path.iterdir()) == []


@patch("services.document_service.get_db_connection")
def test_upload_removes_file_if_database_insert_fails(
    mock_connection, tmp_path
):
    db = MagicMock()
    connection = mock_connection.return_value.__enter__.return_value

    # First query confirms claim ownership; second query fails on insert.
    connection.execute.side_effect = [
        db,
        RuntimeError("database failure"),
    ]
    db.fetchone.return_value = (101,)

    with pytest.raises(RuntimeError, match="database failure"):
        upload_claim_document(
            10, 101, "ACCIDENT_PHOTO", make_upload(), str(tmp_path)
        )

    # The uploaded file must be removed after the failed database insert.
    assert list(tmp_path.iterdir()) == []

@patch("services.document_service.get_db_connection")
def test_get_claim_documents_returns_metadata(mock_connection):
    db = MagicMock()
    mock_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
        (1, "ACCIDENT_PHOTO", "PENDING", "uploaded-time")
    ]

    result = get_claim_documents(10, 101)

    assert result == [
        {
            "document_id": 1,
            "document_type": "ACCIDENT_PHOTO",
            "verification_status": "PENDING",
            "uploaded_at": "uploaded-time",
        }
    ]


@patch("services.document_service.get_db_connection")
def test_get_staff_claim_documents_invalid_id(mock_connection):
    assert get_staff_claim_documents(0) == []
    assert get_staff_claim_documents("1") == []
    mock_connection.assert_not_called()


@patch("services.document_service.get_db_connection")
def test_get_staff_claim_documents_returns_metadata(mock_connection):
    db = MagicMock()
    conn = mock_connection.return_value.__enter__.return_value
    conn.cursor.return_value.__enter__.return_value = db
    db.description = [
        SimpleNamespace(name="document_id"),
        SimpleNamespace(name="document_type"),
        SimpleNamespace(name="verification_status"),
    ]
    db.fetchall.return_value = [(1, "POLICE_REPORT", "VERIFIED")]

    result = get_staff_claim_documents(101)

    assert result == [
        {
            "document_id": 1,
            "document_type": "POLICE_REPORT",
            "verification_status": "VERIFIED",
        }
    ]


@pytest.mark.parametrize(
    ("document_id", "reviewer_id", "status", "notes", "message"),
    [
        (0, 5, "VERIFIED", None, "Invalid document ID."),
        (1, 0, "VERIFIED", None, "Invalid reviewer ID."),
        (1, 5, "PENDING", None,
         "Invalid document verification status."),
        (1, 5, "VERIFIED", 123, "Review notes must be text."),
    ],
)
def test_review_claim_document_validation(
    document_id, reviewer_id, status, notes, message
):
    with patch("services.document_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match=message):
            review_claim_document(
                document_id, reviewer_id, status, notes
            )

        mock_db.assert_not_called()


@patch("services.document_service.get_db_connection")
def test_review_claim_document_success(mock_connection):
    conn = mock_connection.return_value.__enter__.return_value
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (7,)

    result = review_claim_document(
        7, 5, "VERIFIED", "Documents are clear"
    )

    assert result == 7
    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == (
        "VERIFIED", 5, "Documents are clear", 7
    )


@patch("services.document_service.get_db_connection")
def test_review_claim_document_not_found(mock_connection):
    conn = mock_connection.return_value.__enter__.return_value
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None

    with pytest.raises(ValueError, match="Document not found"):
        review_claim_document(7, 5, "REJECTED")

