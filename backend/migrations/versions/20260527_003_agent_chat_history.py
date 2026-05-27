"""
Add agent columns to chat_history table

Revision ID: 003
Revises: 002
Create Date: 2026-05-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_history",
        sa.Column("role", sa.String(20), server_default="user", nullable=False, comment="角色: user/assistant/tool/system"),
    )
    op.add_column(
        "chat_history",
        sa.Column("tool_calls", sa.JSON(), nullable=True, comment="LLM工具调用数组"),
    )
    op.add_column(
        "chat_history",
        sa.Column("metadata", sa.JSON(), nullable=True, comment="附加元数据"),
    )
    # 修改 question 列允许空字符串
    op.alter_column("chat_history", "question", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.drop_column("chat_history", "metadata")
    op.drop_column("chat_history", "tool_calls")
    op.drop_column("chat_history", "role")
