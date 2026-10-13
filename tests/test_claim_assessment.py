from unittest.mock import MagicMock, patch

import pytest

from services.claim_service import create_claim_assessment


@patch("services.claim_service.start_sla")
@patch("services.claim_service.complete_sla")
@patch("services.claim_service.get_db_connection")
def test_assessment_recommendation_moves_claim_to_approval_pending(
    mock_get_connection,
    mock_complete_sla,
    mock_start_sla,
):
    connection = MagicMock()
    cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor

    # Existing claim is eligible for assessment.
    cursor.fetchone.side_effect = [
        ("SUBMITTED",),
        (456,),
    ]

    assessment_id = create_claim_assessment(
        claim_id=99,
        assessor_id=3,
        damage_description="Front bumper damage",
        estimated_repair_cost="1500.00",
        recommendation="RECOMMEND_APPROVAL",
        assessment_notes="Damage reviewed",
    )

    assert assessment_id == 456

    # Confirm that the claim status was updated.
    status_updates = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE claims" in call.args[0]
    ]
    assert len(status_updates) == 1
    assert status_updates[0].args[1] == ("APPROVAL_PENDING", 99)

    # Confirm that the previous and next SLA stages were handled.
    mock_complete_sla.assert_called_once_with(
        99, "SUBMITTED", connection
    )
    mock_start_sla.assert_called_once_with(
        99, "APPROVAL_PENDING", connection
    )


@patch("services.claim_service.get_db_connection")
def test_assessment_rejects_claim_in_ineligible_status(mock_get_connection):
    connection = MagicMock()
    cursor = MagicMock()

    mock_get_connection.return_value.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.return_value = ("SETTLED",)

    with pytest.raises(ValueError, match="not currently eligible"):
        create_claim_assessment(
            claim_id=99,
            assessor_id=3,
            damage_description="Front bumper damage",
            estimated_repair_cost="1500.00",
            recommendation="RECOMMEND_APPROVAL",
        )

    # No assessment should be inserted for an ineligible claim.
    assessment_inserts = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO assessments" in call.args[0]
    ]
    assert assessment_inserts == []


@patch("services.claim_service.start_sla")
@patch("services.claim_service.complete_sla")
@patch("services.claim_service.get_db_connection")
def test_assessment_reuses_supplied_connection(
    mock_get_connection,
    mock_complete_sla,
    mock_start_sla,
):
    connection = MagicMock()
    cursor = MagicMock()

    connection.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [
        ("SUBMITTED",),
        (789,),
    ]

    assessment_id = create_claim_assessment(
        claim_id=101,
        assessor_id=4,
        damage_description="Rear bumper damage",
        estimated_repair_cost="800.00",
        recommendation="RECOMMEND_APPROVAL",
        conn=connection,
    )

    assert assessment_id == 789
    mock_get_connection.assert_not_called()
    connection.cursor.assert_called_once()
    mock_complete_sla.assert_called_once_with(
        101, "SUBMITTED", connection
    )
    mock_start_sla.assert_called_once_with(
        101, "APPROVAL_PENDING", connection
    )
