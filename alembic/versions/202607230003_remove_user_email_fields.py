"""remove user email fields

Revision ID: 202607230003
Revises: 202607230002
Create Date: 2026-07-23
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607230003"
down_revision: str | None = "202607230002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite не поддерживает DROP COLUMN во всех целевых вариантах одинаково,
    # поэтому используем batch mode: Alembic безопасно пересоздаст таблицу.
    with op.batch_alter_table("contact_requests") as batch_op:
        batch_op.drop_column("user_email_error")
        batch_op.drop_column("user_email_status")


def downgrade() -> None:
    with op.batch_alter_table("contact_requests") as batch_op:
        batch_op.add_column(
            sa.Column(
                "user_email_status",
                sa.String(length=32),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(sa.Column("user_email_error", sa.String(length=1000), nullable=True))

    with op.batch_alter_table("contact_requests") as batch_op:
        batch_op.alter_column("user_email_status", server_default=None)
