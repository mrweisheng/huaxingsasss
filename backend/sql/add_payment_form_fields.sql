-- 收支录入表单化改造：新增账户关联 + 凭证异步校验字段
-- 对应需求：合同卡片入口改走结构化表单；收入凭证强制上传并异步校验，不符则不参与结算。

-- 1. 收入关联己方收款账户（payment_accounts 表已存在，见 payment_accounts.sql / PaymentAccount 模型）
ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_account_id INTEGER REFERENCES payment_accounts(id) ON DELETE SET NULL;
COMMENT ON COLUMN payments.payment_account_id IS '收款账户ID（仅income使用，关联己方预设账户）';

-- 2. 支出对方账户（户名/卡号/开户行等，存JSON，不单独建表——供应商不固定）
ALTER TABLE payments ADD COLUMN IF NOT EXISTS counterparty_account JSON;
COMMENT ON COLUMN payments.counterparty_account IS '对方收款账户（仅expense使用）{account_name, account_number, bank_name, branch}';

-- 3. 凭证校验状态（独立于结算状态 status，避免二义性）
ALTER TABLE payments ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20);
COMMENT ON COLUMN payments.verification_status IS '凭证校验状态: pending(校验中)/passed(通过)/failed(不符)/null(未触发校验，如支出无凭证)';

-- 4. 校验明细（AI 提取 vs 表单填写 的对比结果）
ALTER TABLE payments ADD COLUMN IF NOT EXISTS verification_result JSON;
COMMENT ON COLUMN payments.verification_result IS '校验明细 {expected, extracted, match:{amount,payer}, confidence, reason}';

-- 5. 校验完成时间
ALTER TABLE payments ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
COMMENT ON COLUMN payments.verified_at IS '凭证校验完成时间';

-- 索引：校验状态用于列表筛选/置顶排序
CREATE INDEX IF NOT EXISTS idx_payments_verification_status ON payments(verification_status);
