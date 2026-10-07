"""seed configurable insurance rules

Revision ID: 596f37b7ecaa
Revises: 78f73f8c244d
Create Date: 2026-10-07 11:07:11.620887

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '596f37b7ecaa'
down_revision: Union[str, Sequence[str], None] = '78f73f8c244d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Seed the default configurable insurance rules."""

    rules_table = sa.table(
        "rules",
        sa.column("rule_code", sa.String),
        sa.column("rule_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("rule_type", sa.String),
        sa.column("numeric_value", sa.Numeric),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        rules_table,
        [
            {
                "rule_code": "AUTO_APPROVE_LIMIT",
                "rule_name": "Automatic Approval Limit",
                "description": "Claims at or below this amount can qualify for automatic approval when no prior claims exist in the previous 12 months.",
                "rule_type": "AMOUNT",
                "numeric_value": 1000,
                "is_active": True,
            },
            {
                "rule_code": "SUPERVISOR_REVIEW_LIMIT",
                "rule_name": "Supervisor Review Limit",
                "description": "Claims above this amount must be routed for supervisor review.",
                "rule_type": "AMOUNT",
                "numeric_value": 25000,
                "is_active": True,
            },
            {
                "rule_code": "EARLY_LOSS_DAYS",
                "rule_name": "Early Loss Detection Window",
                "description": "Claims reported within this many days of policy start should be flagged for fraud review.",
                "rule_type": "DAYS",
                "numeric_value": 30,
                "is_active": True,
            },
            {
                "rule_code": "ANNUAL_CLAIM_COUNT",
                "rule_name": "Annual Claim Count Threshold",
                "description": "Three or more claims within a 12-month period should trigger a fraud review.",
                "rule_type": "COUNT",
                "numeric_value": 3,
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    """Remove the seeded insurance rules."""

    op.execute(
        """
        DELETE FROM rules
        WHERE rule_code IN (
            'AUTO_APPROVE_LIMIT',
            'SUPERVISOR_REVIEW_LIMIT',
            'EARLY_LOSS_DAYS',
            'ANNUAL_CLAIM_COUNT'
        )
        """
    )