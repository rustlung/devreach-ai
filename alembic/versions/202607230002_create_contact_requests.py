"""create contact requests

Revision ID: 202607230002
Revises: 202607230001
Create Date: 2026-07-23
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607230002"
down_revision: str | None = "202607230001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contact_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("sentiment", sa.String(length=32), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("priority", sa.String(length=32), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("suggested_reply", sa.Text(), nullable=True),
        sa.Column("ai_status", sa.String(length=32), nullable=False),
        sa.Column("ai_error", sa.String(length=1000), nullable=True),
        sa.Column("owner_email_status", sa.String(length=32), nullable=False),
        sa.Column("owner_email_error", sa.String(length=1000), nullable=True),
        sa.Column("user_email_status", sa.String(length=32), nullable=False),
        sa.Column("user_email_error", sa.String(length=1000), nullable=True),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_requests_created_at", "contact_requests", ["created_at"], unique=False)
    op.create_index("ix_contact_requests_processing_status", "contact_requests", ["processing_status"], unique=False)
    op.create_index("ix_contact_requests_email", "contact_requests", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_contact_requests_email", table_name="contact_requests")
    op.drop_index("ix_contact_requests_processing_status", table_name="contact_requests")
    op.drop_index("ix_contact_requests_created_at", table_name="contact_requests")
    op.drop_table("contact_requests")
