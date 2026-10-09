from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from services.claim_service import register_claim


@patch("services.claim_service.save_fraud_flags")
@patch("services.claim_service.save_rule_evaluations")
@patch("services.claim_service.evaluate_claim_rules")
@patch("services.claim_service.get_db_connection")
def test_register_claim_saves_outbox_event(
    mock_get_connection,
    mock_evaluate_rules,
    mock_save_rules,
    mock_save_fraud,
):
    connection = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = connection

    mock_evaluate_rules.return_value = {}

    connection.execute.return_value.fetchone.return_value = (
        12,
        "CLM-TEST-123456",
        5,
        date.today(),
        "Test accident",
        Decimal("1000.00"),
        "SUBMITTED",
        None,
    )

    register_claim(
        customer_id=2,
        policy_id=5,
        incident_date=date.today().isoformat(),
        incident_description="Test accident",
        claimed_amount="1000.00",
    )

    outbox_calls = [
        call for call in connection.execute.call_args_list
        if "INSERT INTO event_outbox" in call.args[0]
    ]

    assert len(outbox_calls) == 1
    assert outbox_calls[0].args[1][0] == "CLAIM"
    assert outbox_calls[0].args[1][1] == 12
    assert outbox_calls[0].args[1][2] == "CLAIM_SUBMITTED"
