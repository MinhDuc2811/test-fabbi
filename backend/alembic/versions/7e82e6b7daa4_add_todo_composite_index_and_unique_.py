"""add todo composite index and unique email index

Revision ID: 7e82e6b7daa4
Revises: a0790c76a129
Create Date: 2026-09-15 14:36:19.766511

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e82e6b7daa4'
down_revision: Union[str, None] = 'a0790c76a129'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: on a large, already-populated production table, prefer
    # `CREATE INDEX CONCURRENTLY` (run outside a transaction, e.g. with
    # Alembic's `with op.get_context().autocommit_block():`) so this does not
    # hold a write-blocking lock for the duration of the index build. Kept as
    # a plain transactional index here since this migration targets the
    # assessment's own dataset.
    op.create_index(
        "ix_todos_user_id_completed_created_at",
        "todos",
        ["user_id", "completed", "created_at"],
        unique=False,
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_index("ix_todos_user_id_completed_created_at", table_name="todos")
