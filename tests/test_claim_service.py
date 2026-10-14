
from unittest.mock import patch

import pytest

from services.claim_service import (
    register_claim,
    record_claim_decision,
    create_claim_assessment,
)


@pytest.mark.parametrize("customer_id", [0, -1, True, "2", None])
def test_register_claim_rejects_invalid_customer_id(customer_id):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="Invalid customer account"):
            register_claim(
                customer_id=customer_id,
                policy_id=5,
                incident_date="2026-10-01",
                incident_description="Vehicle accident",
                claimed_amount="1000.00",
            )

        mock_db.assert_not_called()


@pytest.mark.parametrize("policy_id", [0, -1, True, "5", None])
def test_register_claim_rejects_invalid_policy_id(policy_id):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="valid insurance policy"):
            register_claim(
                customer_id=2,
                policy_id=policy_id,
                incident_date="2026-10-01",
                incident_description="Vehicle accident",
                claimed_amount="1000.00",
            )

        mock_db.assert_not_called()


@pytest.mark.parametrize(
    "description",
    [None, 123, "", "   ", "x" * 5001],
)
def test_register_claim_rejects_invalid_description(description):
    with patch("services.claim_service.get_db_connection") as mock_db:
        expected_message = (
            "Incident description must be 5000 characters or fewer"
            if isinstance(description, str) and len(description) > 5000
            else "Incident description"
        )

        with pytest.raises(ValueError, match=expected_message):
            register_claim(
                customer_id=2,
                policy_id=5,
                incident_date="2026-10-01",
                incident_description=description,
                claimed_amount="1000.00",
            )

        mock_db.assert_not_called()

@pytest.mark.parametrize(
    "incident_date",
    ["not-a-date", "2026-13-01", "", None],
)
def test_register_claim_rejects_invalid_incident_date(incident_date):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="valid incident date"):
            register_claim(
                customer_id=2,
                policy_id=5,
                incident_date=incident_date,
                incident_description="Vehicle accident",
                claimed_amount="1000.00",
            )

        mock_db.assert_not_called()


def test_register_claim_rejects_future_incident_date():
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="cannot be in the future"):
            register_claim(
                customer_id=2,
                policy_id=5,
                incident_date="2099-01-01",
                incident_description="Vehicle accident",
                claimed_amount="1000.00",
            )

        mock_db.assert_not_called()

@pytest.mark.parametrize(
    "amount",
    ["abc", None, "NaN", "Infinity"],
)
def test_register_claim_rejects_invalid_amount(amount):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError):
            register_claim(
                customer_id=2,
                policy_id=5,
                incident_date="2026-10-01",
                incident_description="Vehicle accident",
                claimed_amount=amount,
            )

        mock_db.assert_not_called()


@pytest.mark.parametrize("amount", ["0", "-1", "0.00"])
def test_register_claim_rejects_non_positive_amount(amount):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="greater than zero"):
            register_claim(
                customer_id=2,
                policy_id=5,
                incident_date="2026-10-01",
                incident_description="Vehicle accident",
                claimed_amount=amount,
            )

        mock_db.assert_not_called()


def test_register_claim_rejects_amount_with_more_than_two_decimal_places():
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="two decimal places"):
            register_claim(
                customer_id=2,
                policy_id=5,
                incident_date="2026-10-01",
                incident_description="Vehicle accident",
                claimed_amount="1000.123",
            )

        mock_db.assert_not_called()


def test_register_claim_rejects_excessively_large_amount():
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="too large"):
            register_claim(
                customer_id=2,
                policy_id=5,
                incident_date="2026-10-01",
                incident_description="Vehicle accident",
                claimed_amount="10000000000",
            )

        mock_db.assert_not_called()

def test_register_claim_rejects_ineligible_policy():
    from unittest.mock import MagicMock

    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = None

    with patch(
        "services.claim_service.get_db_connection"
    ) as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = connection

        with pytest.raises(
            ValueError,
            match="not eligible for this claim",
        ):
            register_claim(
                customer_id=2,
                policy_id=5,
                incident_date="2026-10-01",
                incident_description="Vehicle accident",
                claimed_amount="1000.00",
            )

    # Only the policy lookup should execute; no claim is inserted.
    assert connection.execute.call_count == 1
    assert "SELECT policy_id, start_date" in (
        connection.execute.call_args.args[0]
    )


from datetime import date, datetime
from unittest.mock import MagicMock, patch

from services.claim_service import get_customer_claims


def test_get_customer_claims_returns_customer_claims():
    connection = MagicMock()
    connection.execute.return_value.fetchall.return_value = [
        (
            10,
            "CLM-TEST001",
            5,
            "POL-TEST001",
            date(2026, 10, 1),
            "Vehicle accident",
            15000.00,
            "SUBMITTED",
            datetime(2026, 10, 2, 10, 30),
        )
    ]

    with patch(
        "services.claim_service.get_db_connection"
    ) as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = connection

        result = get_customer_claims(customer_id=2)

    assert len(result) == 1
    assert result[0]["claim_id"] == 10
    assert result[0]["claim_number"] == "CLM-TEST001"
    assert result[0]["policy_number"] == "POL-TEST001"
    assert result[0]["status"] == "SUBMITTED"

    query, parameters = connection.execute.call_args.args
    assert "WHERE p.customer_id = %s" in query
    assert "ORDER BY c.created_at DESC" in query
    assert parameters == (2,)


def test_get_customer_claims_returns_empty_list():
    connection = MagicMock()
    connection.execute.return_value.fetchall.return_value = []

    with patch(
        "services.claim_service.get_db_connection"
    ) as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = connection

        result = get_customer_claims(customer_id=2)

    assert result == []

from services.claim_service import get_customer_claim_details


def test_get_customer_claim_details_returns_matching_claim():
    from datetime import date, datetime
    from unittest.mock import MagicMock, patch

    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (
        10,
        "CLM-TEST001",
        5,
        "POL-TEST001",
        date(2026, 10, 1),
        "Vehicle accident",
        15000.00,
        "SUBMITTED",
        "LOW",
        datetime(2026, 10, 5, 12, 0),
        datetime(2026, 10, 2, 10, 30),
        datetime(2026, 10, 2, 10, 30),
    )

    with patch(
        "services.claim_service.get_db_connection"
    ) as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = connection

        result = get_customer_claim_details(
            customer_id=2,
            claim_id=10,
        )

    assert result is not None
    assert result["claim_id"] == 10
    assert result["policy_number"] == "POL-TEST001"
    assert result["fraud_risk_level"] == "LOW"
    assert result["status"] == "SUBMITTED"

    query, parameters = connection.execute.call_args.args
    assert "WHERE p.customer_id = %s" in query
    assert "AND c.claim_id = %s" in query
    assert parameters == (2, 10)


def test_get_customer_claim_details_returns_none_when_not_found():
    from unittest.mock import MagicMock, patch

    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = None

    with patch(
        "services.claim_service.get_db_connection"
    ) as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = connection

        result = get_customer_claim_details(
            customer_id=2,
            claim_id=999,
        )

    assert result is None

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from services.claim_service import get_staff_claim_queue


def test_get_staff_claim_queue_returns_claims():
    connection = MagicMock()
    connection.execute.return_value.fetchall.return_value = [
        (
            10,
            "CLM-TEST001",
            "POL-TEST001",
            date(2026, 10, 1),
            15000.00,
            "SUBMITTED",
            "LOW",
            datetime(2026, 10, 2, 10, 30),
        )
    ]

    with patch(
        "services.claim_service.get_db_connection"
    ) as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = connection

        result = get_staff_claim_queue()

    assert len(result) == 1
    assert result[0]["claim_id"] == 10
    assert result[0]["claim_number"] == "CLM-TEST001"
    assert result[0]["policy_number"] == "POL-TEST001"
    assert result[0]["status"] == "SUBMITTED"
    assert result[0]["fraud_risk_level"] == "LOW"

    query = connection.execute.call_args.args[0]
    assert "ORDER BY" in query
    assert "c.created_at ASC" in query
    assert "c.claim_id ASC" in query


def test_get_staff_claim_queue_returns_empty_list():
    connection = MagicMock()
    connection.execute.return_value.fetchall.return_value = []

    with patch(
        "services.claim_service.get_db_connection"
    ) as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = connection

        result = get_staff_claim_queue()

    assert result == []

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.claim_service import get_staff_claim_details


def test_get_staff_claim_details_returns_claim_and_settlement_data():
    connection = MagicMock()
    cursor = MagicMock()

    cursor.description = [
        SimpleNamespace(name="claim_id"),
        SimpleNamespace(name="claim_number"),
        SimpleNamespace(name="status"),
        SimpleNamespace(name="payment_reference"),
    ]
    cursor.fetchone.return_value = (
        10,
        "CLM-TEST001",
        "SETTLED",
        "PAY-TEST001",
    )

    connection.cursor.return_value.__enter__.return_value = cursor

    with patch(
        "services.claim_service.get_db_connection",
        return_value=connection,
    ):
        result = get_staff_claim_details(10)

    assert result == {
        "claim_id": 10,
        "claim_number": "CLM-TEST001",
        "status": "SETTLED",
        "payment_reference": "PAY-TEST001",
    }
    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == (10,)


def test_get_staff_claim_details_returns_none_when_claim_not_found():
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    connection.cursor.return_value.__enter__.return_value = cursor

    with patch(
        "services.claim_service.get_db_connection",
        return_value=connection,
    ):
        result = get_staff_claim_details(999)

    assert result is None


@pytest.mark.parametrize("claim_id", [0, -1, True, "10", None])
def test_get_staff_claim_details_rejects_invalid_claim_id(claim_id):
    with patch(
        "services.claim_service.get_db_connection"
    ) as mock_get_db:
        result = get_staff_claim_details(claim_id)

    assert result is None
    mock_get_db.assert_not_called()


from services.claim_service import create_claim_assessment


@pytest.mark.parametrize("claim_id", [0, -1, True, "1", None])
def test_create_claim_assessment_rejects_invalid_claim_id(claim_id):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="Invalid claim ID"):
            create_claim_assessment(
                claim_id, 2, "Front bumper damage", "1000.00",
                "RECOMMEND_APPROVAL"
            )
        mock_db.assert_not_called()


@pytest.mark.parametrize("assessor_id", [0, -1, True, "2", None])
def test_create_claim_assessment_rejects_invalid_assessor_id(assessor_id):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="Invalid assessor ID"):
            create_claim_assessment(
                1, assessor_id, "Front bumper damage", "1000.00",
                "RECOMMEND_APPROVAL"
            )
        mock_db.assert_not_called()


@pytest.mark.parametrize(
    "description",
    [None, 123, "", "   ", "x" * 5001],
)
def test_create_claim_assessment_rejects_invalid_damage_description(
    description,
):
    expected_message = (
        "Damage description is required."
        if not isinstance(description, str) or not description.strip()
        else "Damage description is too long."
    )
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match=expected_message):
            create_claim_assessment(
                1, 2, description, "1000.00", "RECOMMEND_APPROVAL"
            )
        mock_db.assert_not_called()


def test_create_claim_assessment_rejects_invalid_recommendation():
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="Invalid assessment recommendation"):
            create_claim_assessment(
                1, 2, "Front bumper damage", "1000.00", "APPROVED"
            )
        mock_db.assert_not_called()


@pytest.mark.parametrize(
    "notes, expected_message",
    [
        (123, "Assessment notes must be text."),
        ("x" * 5001, "Assessment notes are too long."),
    ],
)
def test_create_claim_assessment_rejects_invalid_notes(
    notes, expected_message
):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match=expected_message):
            create_claim_assessment(
                1, 2, "Front bumper damage", "1000.00",
                "RECOMMEND_APPROVAL", assessment_notes=notes
            )
        mock_db.assert_not_called()


@pytest.mark.parametrize(
    "repair_cost, expected_message",
    [
        ("not-a-number", "Estimated repair cost must be a valid number."),
        (None, "Estimated repair cost must be a valid number."),
        ("NaN", "Estimated repair cost cannot be negative."),
        ("Infinity", "Estimated repair cost cannot be negative."),
        ("-1.00", "Estimated repair cost cannot be negative."),
        ("10.123", "Estimated repair cost supports up to two decimal places."),
        ("10000000000", "Estimated repair cost is too large."),
    ],
)
def test_create_claim_assessment_rejects_invalid_repair_cost(
    repair_cost, expected_message
):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match=expected_message):
            create_claim_assessment(
                1, 2, "Front bumper damage", repair_cost,
                "RECOMMEND_APPROVAL"
            )
        mock_db.assert_not_called()


from services.claim_service import create_claim_assessment


def test_create_claim_assessment_rejects_missing_claim():
    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None

        with pytest.raises(ValueError, match="Claim not found"):
            create_claim_assessment(
                1, 2, "Front bumper damage", "1000.00",
                "RECOMMEND_APPROVAL"
            )

        cursor.execute.assert_called_once()


def test_create_claim_assessment_rejects_ineligible_claim_status():
    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ("SETTLED",)

        with pytest.raises(
            ValueError, match="not currently eligible for assessment"
        ):
            create_claim_assessment(
                1, 2, "Front bumper damage", "1000.00",
                "RECOMMEND_APPROVAL"
            )

        cursor.execute.assert_called_once()

from services.claim_service import get_claim_assessments


@pytest.mark.parametrize("claim_id", [0, -1, "1", None])
def test_get_claim_assessments_rejects_invalid_claim_id(claim_id):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="Invalid claim ID"):
            get_claim_assessments(claim_id)

        mock_db.assert_not_called()


def test_get_claim_assessments_returns_assessment_records():
    row = (
        10,
        1,
        "Front bumper damage",
        1000.00,
        "RECOMMEND_APPROVAL",
        "Repair recommended",
        None,
        "lokesh.assessor",
        "Lokesh Assessor",
    )

    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [row]

        result = get_claim_assessments(1)

    assert len(result) == 1
    assert result[0]["assessment_id"] == 10
    assert result[0]["recommendation"] == "RECOMMEND_APPROVAL"
    assert result[0]["assessor_username"] == "lokesh.assessor"


def test_get_claim_assessments_returns_empty_list():
    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []

        result = get_claim_assessments(1)

    assert result == []


@pytest.mark.parametrize("claim_id", [0, -1, True, "1", None])
def test_record_claim_decision_rejects_invalid_claim_id(claim_id):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="Invalid claim ID"):
            record_claim_decision(
                claim_id, 2, "APPROVED", "Decision reason"
            )

        mock_db.assert_not_called()


@pytest.mark.parametrize("approver_id", [0, -1, True, "2", None])
def test_record_claim_decision_rejects_invalid_approver_id(approver_id):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="Invalid approver ID"):
            record_claim_decision(
                1, approver_id, "APPROVED", "Decision reason"
            )

        mock_db.assert_not_called()


@pytest.mark.parametrize(
    "decision",
    ["INVALID", "approved", "", None],
)
def test_record_claim_decision_rejects_invalid_decision(decision):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="Invalid claim decision"):
            record_claim_decision(
                1, 2, decision, "Decision reason"
            )

        mock_db.assert_not_called()


@pytest.mark.parametrize("reason", [None, 123, "", "   "])
def test_record_claim_decision_rejects_missing_reason(reason):
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="A decision reason is required"):
            record_claim_decision(1, 2, "APPROVED", reason)

        mock_db.assert_not_called()


def test_record_claim_decision_rejects_reason_over_5000_characters():
    with patch("services.claim_service.get_db_connection") as mock_db:
        with pytest.raises(ValueError, match="Decision reason is too long"):
            record_claim_decision(
                1, 2, "APPROVED", "x" * 5001
            )

        mock_db.assert_not_called()


def test_record_claim_decision_rejects_missing_claim():
    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None

        with pytest.raises(ValueError, match="Claim not found"):
            record_claim_decision(
                999, 2, "APPROVED", "Decision reason"
            )

        cursor.execute.assert_called_once()


def test_record_claim_decision_rejects_ineligible_claim_status():
    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ("SUBMITTED",)

        with pytest.raises(
            ValueError,
            match="Claim must be in APPROVAL_PENDING status",
        ):
            record_claim_decision(
                1, 2, "APPROVED", "Decision reason"
            )

        cursor.execute.assert_called_once()


def test_record_claim_decision_rejects_claim_without_assessment():
    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            ("APPROVAL_PENDING",),
            (False,),
        ]

        with pytest.raises(
            ValueError,
            match="An assessment is required before a decision",
        ):
            record_claim_decision(
                1, 2, "APPROVED", "Decision reason"
            )

        assert cursor.execute.call_count == 2


def test_record_claim_decision_blocks_approval_with_open_fraud_flags():
    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            ("APPROVAL_PENDING",),
            (True,),
            (True,),
        ]

        with pytest.raises(
            ValueError,
            match="unresolved fraud flags require review",
        ):
            record_claim_decision(
                1, 2, "APPROVED", "Decision reason"
            )

        assert cursor.execute.call_count == 3


def test_record_claim_decision_successfully_approves_claim():
    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            ("APPROVAL_PENDING",),  # Current claim status
            (True,),                 # Assessment exists
            (False,),                # No unresolved fraud flags
            (42,),                   # New decision ID
        ]

        result = record_claim_decision(
            1, 2, "APPROVED", "  Repairs approved  "
        )

    assert result == 42

    # Verify the claim status is updated to APPROVED.
    update_call = next(
        call for call in cursor.execute.call_args_list
        if "UPDATE claims" in call.args[0]
    )
    assert update_call.args[1] == ("APPROVED", 1)

    # Verify the decision reason is trimmed before saving.
    decision_call = next(
        call for call in cursor.execute.call_args_list
        if "INSERT INTO claim_decisions" in call.args[0]
    )
    assert decision_call.args[1] == (
        1, 2, "APPROVED", "Repairs approved"
    )

    # Verify the status history is recorded.
    history_call = next(
        call for call in cursor.execute.call_args_list
        if "INSERT INTO claim_status_history" in call.args[0]
    )
    assert history_call.args[1] == (
        1, "APPROVAL_PENDING", "APPROVED", 2, "Repairs approved"
    )


def test_record_claim_decision_successfully_rejects_claim():
    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            ("APPROVAL_PENDING",),  # Current claim status
            (True,),                 # Assessment exists
            (73,),                   # New decision ID
        ]

        result = record_claim_decision(
            1, 2, "REJECTED", "Damage is not covered"
        )

    assert result == 73

    update_call = next(
        call for call in cursor.execute.call_args_list
        if "UPDATE claims" in call.args[0]
    )
    assert update_call.args[1] == ("REJECTED", 1)

    history_call = next(
        call for call in cursor.execute.call_args_list
        if "INSERT INTO claim_status_history" in call.args[0]
    )
    assert history_call.args[1] == (
        1, "APPROVAL_PENDING", "REJECTED", 2,
        "Damage is not covered"
    )


def test_record_claim_decision_requests_more_information():
    with patch("services.claim_service.get_db_connection") as mock_db:
        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            ("APPROVAL_PENDING",),  # Current claim status
            (True,),                 # Assessment exists
            (84,),                   # New decision ID
        ]

        result = record_claim_decision(
            1, 2, "MORE_INFORMATION_REQUIRED",
            "Please provide the repair invoice"
        )

    assert result == 84

    update_call = next(
        call for call in cursor.execute.call_args_list
        if "UPDATE claims" in call.args[0]
    )
    assert update_call.args[1] == ("UNDER_REVIEW", 1)

    history_call = next(
        call for call in cursor.execute.call_args_list
        if "INSERT INTO claim_status_history" in call.args[0]
    )
    assert history_call.args[1] == (
        1, "APPROVAL_PENDING", "UNDER_REVIEW", 2,
        "Please provide the repair invoice"
    )


def test_create_claim_assessment_routes_approval_recommendation():
    with patch("services.claim_service.get_db_connection") as mock_db, \
         patch("services.claim_service.complete_sla") as mock_complete_sla, \
         patch("services.claim_service.start_sla") as mock_start_sla:

        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value

        # First fetch returns the claim's current status.
        # Second fetch returns the newly created assessment ID.
        cursor.fetchone.side_effect = [
            ("SUBMITTED",),
            (42,),
        ]

        assessment_id = create_claim_assessment(
            claim_id=1,
            assessor_id=2,
            damage_description="Front bumper damage",
            estimated_repair_cost="1000.00",
            recommendation="RECOMMEND_APPROVAL",
            assessment_notes="Repair recommended",
        )

        assert assessment_id == 42

        executed_sql = [
            call.args[0]
            for call in cursor.execute.call_args_list
        ]

        assert any(
            "INSERT INTO assessments" in sql
            for sql in executed_sql
        )

        assert any(
            "UPDATE claims" in sql
            for sql in executed_sql
        )

        assert any(
            "INSERT INTO claim_status_history" in sql
            for sql in executed_sql
        )

        mock_complete_sla.assert_called_once_with(
            1, "SUBMITTED", connection
        )
        mock_start_sla.assert_called_once_with(
            1, "APPROVAL_PENDING", connection
        )

def test_create_claim_assessment_routes_rejection_recommendation():
    with patch("services.claim_service.get_db_connection") as mock_db, \
         patch("services.claim_service.complete_sla") as mock_complete_sla, \
         patch("services.claim_service.start_sla") as mock_start_sla:

        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value

        cursor.fetchone.side_effect = [
            ("SUBMITTED",),
            (43,),
        ]

        assessment_id = create_claim_assessment(
            claim_id=2,
            assessor_id=3,
            damage_description="Severe vehicle damage",
            estimated_repair_cost="25000.00",
            recommendation="RECOMMEND_REJECTION",
            assessment_notes="Damage requires further review",
        )

        assert assessment_id == 43

        executed_sql = [
            call.args[0]
            for call in cursor.execute.call_args_list
        ]

        assert any(
            "INSERT INTO assessments" in sql
            for sql in executed_sql
        )

        update_call = next(
            call for call in cursor.execute.call_args_list
            if "UPDATE claims" in call.args[0]
        )
        assert update_call.args[1] == ("APPROVAL_PENDING", 2)

        mock_complete_sla.assert_called_once_with(
            2, "SUBMITTED", connection
        )
        mock_start_sla.assert_called_once_with(
            2, "APPROVAL_PENDING", connection
        )
def test_create_claim_assessment_routes_more_information():
    with patch("services.claim_service.get_db_connection") as mock_db, \
         patch("services.claim_service.complete_sla") as mock_complete_sla, \
         patch("services.claim_service.start_sla") as mock_start_sla:

        connection = mock_db.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value

        cursor.fetchone.side_effect = [
            ("SUBMITTED",),
            (44,),
        ]

        assessment_id = create_claim_assessment(
            claim_id=3,
            assessor_id=4,
            damage_description="Vehicle damage needs more inspection",
            estimated_repair_cost="12000.00",
            recommendation="MORE_INFORMATION_REQUIRED",
            assessment_notes="Additional repair documents are required",
        )

        assert assessment_id == 44

        executed_sql = [
            call.args[0]
            for call in cursor.execute.call_args_list
        ]

        assert any(
            "INSERT INTO assessments" in sql
            for sql in executed_sql
        )

        update_call = next(
            call for call in cursor.execute.call_args_list
            if "UPDATE claims" in call.args[0]
        )

        assert update_call.args[1] == ("UNDER_REVIEW", 3)

        mock_complete_sla.assert_called_once_with(
            3, "SUBMITTED", connection
        )

        mock_start_sla.assert_called_once_with(
            3, "UNDER_REVIEW", connection
        )
def test_create_claim_assessment_reuses_existing_connection():
    from unittest.mock import MagicMock, patch

    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value

    cursor.fetchone.side_effect = [
        ("SUBMITTED",),
        (45,),
    ]

    with patch("services.claim_service.complete_sla"), \
         patch("services.claim_service.start_sla") as mock_start_sla:

        assessment_id = create_claim_assessment(
            claim_id=4,
            assessor_id=5,
            damage_description="Minor front bumper damage",
            estimated_repair_cost="5000.00",
            recommendation="RECOMMEND_APPROVAL",
            assessment_notes="Assessment completed",
            conn=connection,
        )

    assert assessment_id == 45
    connection.cursor.assert_called_once()
    mock_start_sla.assert_called_once_with(
        4, "APPROVAL_PENDING", connection
    )
def test_register_claim_success_creates_claim_and_outbox_event():
    from unittest.mock import MagicMock, patch
    from datetime import date, datetime
    from decimal import Decimal

    connection = MagicMock()
    claim_row = (
        101,
        "CLM-TEST-101",
        5,
        date(2026, 10, 1),
        "Vehicle accident",
        Decimal("10000.00"),
        "SUBMITTED",
        datetime(2026, 10, 14),
    )

    connection.execute.return_value.fetchone.side_effect = [
        (5, date(2026, 1, 1)),
        claim_row,
    ]

    rules_result = {"rules": [], "fraud_flags": []}

    with patch(
        "services.claim_service.get_db_connection"
    ) as mock_db, patch(
        "services.claim_service.evaluate_claim_rules",
        return_value=rules_result,
    ) as mock_rules, patch(
        "services.claim_service.save_rule_evaluations"
    ) as mock_save_rules, patch(
        "services.claim_service.save_fraud_flags"
    ) as mock_save_fraud:

        mock_db.return_value.__enter__.return_value = connection

        result = register_claim(
            customer_id=2,
            policy_id=5,
            incident_date="2026-10-01",
            incident_description="Vehicle accident",
            claimed_amount="10000.00",
        )

    assert result["claim_id"] == 101
    assert result["status"] == "SUBMITTED"
    mock_rules.assert_called_once()
    mock_save_rules.assert_called_once()
    mock_save_fraud.assert_called_once()

    sql_statements = [
        call.args[0]
        for call in connection.execute.call_args_list
    ]

    assert any("INSERT INTO claims" in sql for sql in sql_statements)
    assert any(
        "INSERT INTO claim_status_history" in sql
        for sql in sql_statements
    )
    assert any(
        "INSERT INTO event_outbox" in sql
        for sql in sql_statements
    )
