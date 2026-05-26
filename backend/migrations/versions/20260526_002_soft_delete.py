"""
Add soft delete columns (is_deleted, deleted_at) to all business tables

Revision ID: 002
Revises: 001
Create Date: 2026-05-26
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


tables_to_update = ["customers", "contracts", "payments", "files"]


def upgrade() -> None:
    for table in tables_to_update:
        op.add_column(
            table,
            sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, comment="软删除标记"),
        )
        op.add_column(
            table,
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, comment="软删除时间"),
        )
        op.create_index(f"idx_{table}_is_deleted", table, ["is_deleted"])


def downgrade() -> None:
    for table in tables_to_update:
        op.drop_index(f"idx_{table}_is_deleted", table_name=table)
        op.drop_column(table, "deleted_at")
        op.drop_column(table, "is_deleted")
