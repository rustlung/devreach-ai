"""foundation baseline

Revision ID: 202607230001
Revises:
Create Date: 2026-07-23
"""

from typing import Sequence

revision: str = "202607230001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Техническая базовая миграция: бизнес-таблицы появятся на следующих этапах."""


def downgrade() -> None:
    """Откат технической миграции не требует действий."""
