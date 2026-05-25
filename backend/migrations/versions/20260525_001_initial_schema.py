"""Initial database schema - Create all tables

Revision ID: 20260525_001
Revises: 
Create Date: 2026-05-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260525_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建所有表"""
    
    # 用户表
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='sales'),
        sa.Column('department', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    
    # 客户表
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('contact_person', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('id_card_number_encrypted', sa.Text(), nullable=True),
        sa.Column('business_license', sa.String(length=50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('wechat_group_name', sa.String(length=200), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('phone IS NOT NULL OR email IS NOT NULL', name='chk_phone_or_email')
    )
    op.create_index(op.f('ix_customers_name'), 'customers', ['name'], unique=False)
    op.create_index(op.f('ix_customers_phone'), 'customers', ['phone'], unique=False)
    op.create_index(op.f('ix_customers_created_by'), 'customers', ['created_by'], unique=False)
    op.create_index(op.f('ix_customers_wechat_group'), 'customers', ['wechat_group_name'], unique=False)
    
    # 合同表
    op.create_table(
        'contracts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('contract_number', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('sales_person_id', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='CNY'),
        sa.Column('total_amount', sa.DECIMAL(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('paid_amount', sa.DECIMAL(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('remaining_amount', sa.DECIMAL(precision=15, scale=2), server_default='total_amount - paid_amount'),
        sa.Column('total_amount_in_cny', sa.DECIMAL(precision=15, scale=2), nullable=True),
        sa.Column('paid_amount_in_cny', sa.DECIMAL(precision=15, scale=2), server_default='0'),
        sa.Column('remaining_amount_in_cny', sa.DECIMAL(precision=15, scale=2), server_default='COALESCE(total_amount_in_cny, 0) - paid_amount_in_cny'),
        sa.Column('original_file_path', sa.String(length=500), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('contract_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('signed_date', sa.Date(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('confidence', sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('needs_review', sa.Boolean(), server_default='false'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['sales_person_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contract_number'),
        sa.CheckConstraint('total_amount >= 0 AND paid_amount >= 0', name='chk_amount_positive'),
        sa.CheckConstraint('COALESCE(paid_amount_in_cny, 0) <= COALESCE(total_amount_in_cny, 0)', name='chk_paid_not_exceed_total_cny')
    )
    op.create_index(op.f('ix_contracts_contract_number'), 'contracts', ['contract_number'], unique=True)
    op.create_index(op.f('ix_contracts_customer_id'), 'contracts', ['customer_id'], unique=False)
    op.create_index(op.f('ix_contracts_sales_person_id'), 'contracts', ['sales_person_id'], unique=False)
    op.create_index(op.f('ix_contracts_status'), 'contracts', ['status'], unique=False)
    op.create_index(op.f('ix_contracts_signed_date'), 'contracts', ['signed_date'], unique=False)
    op.create_index(op.f('ix_contracts_file_hash'), 'contracts', ['file_hash'], unique=False)
    op.create_index('idx_contracts_data_gin', 'contracts', ['contract_data'], unique=False, postgresql_using='gin')
    
    # 付款表
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('contract_id', sa.Integer(), nullable=False),
        sa.Column('installment_number', sa.Integer(), nullable=False),
        sa.Column('installment_name', sa.String(length=50), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='CNY'),
        sa.Column('amount', sa.DECIMAL(precision=15, scale=2), nullable=False),
        sa.Column('paid_amount', sa.DECIMAL(precision=15, scale=2), server_default='0'),
        sa.Column('exchange_rate', sa.DECIMAL(precision=10, scale=6), nullable=True),
        sa.Column('amount_in_cny', sa.DECIMAL(precision=15, scale=2), server_default='amount * COALESCE(exchange_rate, 1)'),
        sa.Column('paid_amount_in_cny', sa.DECIMAL(precision=15, scale=2), server_default='paid_amount * COALESCE(exchange_rate, 1)'),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('paid_date', sa.Date(), nullable=True),
        sa.Column('receipt_image_path', sa.String(length=500), nullable=True),
        sa.Column('receipt_file_hash', sa.String(length=64), nullable=True),
        sa.Column('receipt_ocr_text', sa.Text(), nullable=True),
        sa.Column('payment_method', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('source', sa.String(length=20), server_default='manual'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contract_id', 'installment_number', name='uq_contract_installment'),
        sa.CheckConstraint('amount > 0', name='chk_payment_amount_positive'),
        sa.CheckConstraint('paid_amount <= amount', name='chk_paid_not_exceed_amount')
    )
    op.create_index(op.f('ix_payments_contract_id'), 'payments', ['contract_id'], unique=False)
    op.create_index(op.f('ix_payments_due_date'), 'payments', ['due_date'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
    op.create_index(op.f('ix_payments_currency'), 'payments', ['currency'], unique=False)
    op.create_index(op.f('ix_payments_source'), 'payments', ['source'], unique=False)
    op.create_index('idx_payments_installment', 'payments', ['contract_id', 'installment_number'], unique=False)
    
    # 汇率表
    op.create_table(
        'exchange_rates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('from_currency', sa.String(length=3), nullable=False),
        sa.Column('to_currency', sa.String(length=3), nullable=False, server_default='CNY'),
        sa.Column('rate', sa.DECIMAL(precision=10, scale=6), nullable=False),
        sa.Column('rate_date', sa.Date(), nullable=False),
        sa.Column('source', sa.String(length=20), server_default='manual'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_currency', 'to_currency', 'rate_date', name='uq_currency_date')
    )
    op.create_index(op.f('ix_exchange_rates_from_currency'), 'exchange_rates', ['from_currency'], unique=False)
    op.create_index(op.f('ix_exchange_rates_to_currency'), 'exchange_rates', ['to_currency'], unique=False)
    op.create_index(op.f('ix_exchange_rates_rate_date'), 'exchange_rates', ['rate_date'], unique=False)
    op.create_index(op.f('ix_exchange_rates_is_active'), 'exchange_rates', ['is_active'], unique=False)
    op.create_index('idx_exchange_rates_currencies', 'exchange_rates', ['from_currency', 'to_currency'], unique=False)
    
    # 文件表
    op.create_table(
        'files',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('stored_filename', sa.String(length=500), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('related_type', sa.String(length=20), nullable=False),
        sa.Column('related_id', sa.Integer(), nullable=False),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('ocr_confidence', sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('ai_extracted_data', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_hash', 'related_type', 'related_id', name='uq_file_hash_related')
    )
    op.create_index(op.f('ix_files_file_hash'), 'files', ['file_hash'], unique=False)
    op.create_index(op.f('ix_files_related_type'), 'files', ['related_type'], unique=False)
    op.create_index(op.f('ix_files_related_id'), 'files', ['related_id'], unique=False)
    op.create_index(op.f('ix_files_uploaded_by'), 'files', ['uploaded_by'], unique=False)
    op.create_index('idx_files_related', 'files', ['related_type', 'related_id'], unique=False)
    
    # 审计日志表
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('old_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_type'), 'audit_logs', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    
    # 对话历史表
    op.create_table(
        'chat_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('context_contracts', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('intent_type', sa.String(length=50), nullable=True),
        sa.Column('extracted_entities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sql_query', sa.Text(), nullable=True),
        sa.Column('llm_model', sa.String(length=50), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_history_user_id'), 'chat_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_history_session_id'), 'chat_history', ['session_id'], unique=False)
    op.create_index(op.f('ix_chat_history_created_at'), 'chat_history', ['created_at'], unique=False)
    
    # 插入初始数据
    op.execute("""
        INSERT INTO users (username, password_hash, email, full_name, role, is_active)
        VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4K/8KzO.Qi', 'admin@huaxing.com', '系统管理员', 'admin', true)
    """)
    
    # 插入默认汇率
    op.execute("""
        INSERT INTO exchange_rates (from_currency, to_currency, rate, rate_date, source, remarks, is_active)
        VALUES 
            ('HKD', 'CNY', 0.920000, CURRENT_DATE, 'system', '系统默认汇率', true),
            ('USD', 'CNY', 7.250000, CURRENT_DATE, 'system', '系统默认汇率', true)
    """)


def downgrade() -> None:
    """删除所有表"""
    op.drop_table('chat_history')
    op.drop_table('audit_logs')
    op.drop_table('files')
    op.drop_table('exchange_rates')
    op.drop_table('payments')
    op.drop_table('contracts')
    op.drop_table('customers')
    op.drop_table('users')
