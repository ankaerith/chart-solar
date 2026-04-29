"""baseline

Revision ID: c6cb527d3505
Revises:
Create Date: 2026-04-28 21:44:15.931476

Empty parent revision; subsequent migrations chain off this one.

"""

from collections.abc import Sequence

revision: str = "c6cb527d3505"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
