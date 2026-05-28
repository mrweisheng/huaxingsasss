"""
Add business_type and business_description columns to contracts

Revision ID: 004
Revises: 003
Create Date: 2026-05-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("business_type", sa.String(50), nullable=True, comment="业务类型: 车辆业务/中港牌业务"),
    )
    op.add_column(
        "contracts",
        sa.Column("business_description", sa.String(200), nullable=True, comment="业务描述: 如购买丰田阿尔法30系"),
    )
    op.create_index("idx_contracts_business_type", "contracts", ["business_type"])

    # 回填已有数据：从 contract_data JSON 中提取
    op.execute("""
        UPDATE contracts
        SET business_type = contract_data->>'business_type',
            business_description = contract_data->>'business_description'
        WHERE contract_data->>'business_type' IS NOT NULL
          AND business_type IS NULL
    """)

    # 修复 remaining_amount 为 NULL 的历史数据
    op.execute("""
        UPDATE contracts
        SET remaining_amount = total_amount - COALESCE(paid_amount, 0),
            remaining_amount_in_cny = COALESCE(total_amount_in_cny, 0) - COALESCE(paid_amount_in_cny, 0)
        WHERE remaining_amount IS NULL
    """)


def downgrade() -> None:
    op.drop_index("idx_contracts_business_type")
    op.drop_column("contracts", "business_description")
    op.drop_column("contracts", "business_type")
