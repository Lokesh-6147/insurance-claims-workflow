"""add notification delivery tracking

Revision ID: 8a2c6d1f4b90
Revises: 596f37b7ecaa
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8a2c6d1f4b90"
down_revision: Union[str, Sequence[str], None] = "596f37b7ecaa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column("notification_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event_outbox.event_id"],
            name="fk_notification_deliveries_outbox",
            ondelete="RESTRICT",
        ),
        sa.Column("recipient_email", sa.String(length=254), nullable=False),
        sa.Column("notification_type", sa.String(length=100), nullable=False),
        sa.Column("delivery_status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "event_id",
            "recipient_email",
            "notification_type",
            name="uq_notification_delivery_event_recipient_type",
        ),
        sa.CheckConstraint(
            "delivery_status IN ('PENDING', 'SENDING', 'SENT', 'FAILED')",
            name="chk_notification_delivery_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="chk_notification_delivery_attempt_count",
        ),
    )
    op.create_index(
        "idx_notification_deliveries_status_created",
        "notification_deliveries",
        ["delivery_status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_notification_deliveries_status_created",
        table_name="notification_deliveries",
    )
    op.drop_table("notification_deliveries")
