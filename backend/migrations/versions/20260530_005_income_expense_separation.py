"""
Income/expense separation: add payment type, contract expense fields, migrate roles

Revision ID: 005
Revises: 004
Create Date: 2026-05-30
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. payments 表新增 type 和 payee_name 列
    op.add_column(
        "payments",
        sa.Column("type", sa.String(20), nullable=False, server_default="income",
                   comment="类型: income/expense"),
    )
    op.add_column(
        "payments",
        sa.Column("payee_name", sa.String(200), nullable=True,
                   comment="收款方名称（仅expense使用）"),
    )

    # 2. 回填：现有记录全部标记为 income
    op.execute("UPDATE payments SET type = 'income'")

    # 3. 将 pending_voucher 记录自动确认（代码中将移除此状态）
    op.execute("""
        UPDATE payments
        SET status = 'paid',
            paid_amount = amount,
            paid_amount_in_cny = amount_in_cny
        WHERE status = 'pending_voucher'
    """)

    # 4. 替换唯一约束：加上 type 维度
    op.drop_constraint("uq_contract_installment", "payments", type_="unique")
    op.create_unique_constraint(
        "uq_contract_installment_type", "payments",
        ["contract_id", "installment_number", "type"],
    )

    # 5. 新增 type 索引
    op.create_index("idx_payments_type", "payments", ["type"])

    # 6. contracts 表新增支出汇总列
    op.add_column(
        "contracts",
        sa.Column("total_expense", sa.DECIMAL(15, 2), nullable=True, server_default="0",
                   comment="总支出金额"),
    )
    op.add_column(
        "contracts",
        sa.Column("total_expense_in_cny", sa.DECIMAL(15, 2), nullable=True, server_default="0",
                   comment="总支出折算CNY"),
    )

    # 7. 回填合同支出字段
    op.execute("UPDATE contracts SET total_expense = 0, total_expense_in_cny = 0")

    # 8. 角色迁移：sales/finance/viewer → income
    op.execute("UPDATE users SET role = 'income' WHERE role IN ('sales', 'finance', 'viewer')")

    # 9. 删除不再适用的 CHECK 约束
    op.drop_constraint("chk_paid_not_exceed_total_cny", "contracts", type_="check")


def downgrade() -> None:
    # 恢复 CHECK 约束
    op.execute("""
        ALTER TABLE contracts
        ADD CONSTRAINT chk_paid_not_exceed_total_cny
        CHECK (COALESCE(paid_amount_in_cny, 0) <= COALESCE(total_amount_in_cny, 0))
    """)

    # 还原角色（注意：无法区分原始 finance/viewer，统一还原为 sales）
    op.execute("UPDATE users SET role = 'sales' WHERE role IN ('income', 'expense')")

    # 删除 contracts 新增列
    op.drop_column("contracts", "total_expense_in_cny")
    op.drop_column("contracts", "total_expense")

    # 删除 payments 索引和约束
    op.drop_index("idx_payments_type")
    op.drop_constraint("uq_contract_installment_type", "payments", type_="unique")
    op.create_unique_constraint(
        "uq_contract_installment", "payments",
        ["contract_id", "installment_number"],
    )

    # 删除 payments 新增列
    op.drop_column("payments", "payee_name")
    op.drop_column("payments", "type")
