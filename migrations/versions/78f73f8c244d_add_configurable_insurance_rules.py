"""add configurable insurance rules

Revision ID: 78f73f8c244d
Revises: 0fc528740690
Create Date: 2026-10-07 10:57:42.652484

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78f73f8c244d'
down_revision: Union[str, Sequence[str], None] = '0fc528740690'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Create configurable insurance rules and rule evaluation tables."""

    op.create_table(
        "rules",
        sa.Column("rule_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("rule_code", sa.String(length=50), nullable=False),
        sa.Column("rule_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("rule_type", sa.String(length=30), nullable=False),
        sa.Column("numeric_value", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("rule_code", name="uq_rules_rule_code"),
        sa.CheckConstraint(
            "numeric_value >= 0",
            name="chk_rules_numeric_value",
        ),
    )

    op.create_index(
        "idx_rules_active",
        "rules",
        ["is_active"],
    )

    op.create_table(
        "rule_evaluations",
        sa.Column(
            "evaluation_id",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column("claim_id", sa.BigInteger(), nullable=False),
        sa.Column("rule_id", sa.BigInteger(), nullable=False),
        sa.Column("triggered", sa.Boolean(), nullable=False),
        sa.Column("evaluation_result", sa.Text(), nullable=False),
        sa.Column("evaluated_value", sa.Numeric(12, 2)),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.claim_id"],
            name="fk_rule_evaluations_claim",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["rules.rule_id"],
            name="fk_rule_evaluations_rule",
        ),
    )

    op.create_index(
        "idx_rule_evaluations_claim",
        "rule_evaluations",
        ["claim_id"],
    )

    op.create_index(
        "idx_rule_evaluations_rule",
        "rule_evaluations",
        ["rule_id"],
    )


def downgrade() -> None:
    """Remove configurable insurance rules and evaluations."""

    op.drop_index(
        "idx_rule_evaluations_rule",
        table_name="rule_evaluations",
    )
    op.drop_index(
        "idx_rule_evaluations_claim",
        table_name="rule_evaluations",
    )
    op.drop_table("rule_evaluations")

    op.drop_index(
        "idx_rules_active",
        table_name="rules",
    )
    op.drop_table("rules")
