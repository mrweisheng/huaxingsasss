-- 收款账户表（彻底重建）
-- 删除旧表
DROP TABLE IF EXISTS payment_accounts CASCADE;

-- 创建新表
CREATE TABLE payment_accounts (
    id              SERIAL PRIMARY KEY,
    bank_name       VARCHAR(100) NOT NULL,           -- 银行名称
    account_name    VARCHAR(200) NOT NULL,           -- 户名
    account_number  VARCHAR(100),                    -- 银行账号
    fps_id          VARCHAR(50),                     -- 转数快 FPS ID
    branch          VARCHAR(200),                    -- 网点
    address         VARCHAR(500),                    -- 地址
    phone           VARCHAR(50),                     -- 电话
    swift_code      VARCHAR(50),                     -- SWIFT Code（国际汇款）
    is_default      BOOLEAN DEFAULT FALSE,           -- 是否默认收款账户
    sort_order      INTEGER DEFAULT 0,               -- 排序
    remarks         TEXT,                            -- 备注
    created_by      INTEGER REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    is_deleted      BOOLEAN DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE payment_accounts IS '收款账户表';
COMMENT ON COLUMN payment_accounts.bank_name IS '银行名称';
COMMENT ON COLUMN payment_accounts.account_name IS '户名';
COMMENT ON COLUMN payment_accounts.account_number IS '银行账号';
COMMENT ON COLUMN payment_accounts.fps_id IS '转数快 FPS ID';
COMMENT ON COLUMN payment_accounts.branch IS '网点';
COMMENT ON COLUMN payment_accounts.address IS '地址';
COMMENT ON COLUMN payment_accounts.phone IS '电话';
COMMENT ON COLUMN payment_accounts.swift_code IS 'SWIFT Code';
COMMENT ON COLUMN payment_accounts.is_default IS '是否默认收款账户';

CREATE INDEX IF NOT EXISTS idx_payment_accounts_type ON payment_accounts(is_deleted) WHERE is_deleted = FALSE;

-- 初始数据
INSERT INTO payment_accounts (bank_name, account_name, account_number, fps_id, is_default, sort_order) VALUES
('华侨银行', '高山貿易有限公司', '035-803-185706051', '122842800', TRUE, 1);

INSERT INTO payment_accounts (bank_name, account_name, account_number, branch, address, phone, is_default, sort_order) VALUES
('工商银行', '陈振耀', '2009020501023937427', '汕尾海丰东门头支行（网点号:0205）', '海丰县城人民中路7号', '0660-6623712', FALSE, 2);
