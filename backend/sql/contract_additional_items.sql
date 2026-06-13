-- 合同附加项功能 v2.0：附加项 = 合同应收清单上的一行（车险/保养/人工费等）
-- 说明：
--   * 附加项不是独立财务实体，没有「已收/未收」概念
--   * 客户付款不强制归属到附加项；payments.additional_item_id 仅作可选展示标签，不参与任何金额聚合
--   * contracts.additional_total_by_currency 为冗余汇总字段，避免列表/台账 N+1
-- 逐段执行即可（均幂等）。

-- 1. 附加项明细表
CREATE TABLE IF NOT EXISTS contract_additional_items (
    id              SERIAL PRIMARY KEY,
    contract_id     INTEGER NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,
    name            VARCHAR(200) NOT NULL,          -- 项目名称（车险 / 保养改装 / 人工费）
    amount          DECIMAL(15,2) NOT NULL,         -- 金额
    currency        VARCHAR(3) NOT NULL DEFAULT 'CNY',
    paid_to         VARCHAR(200),                   -- 付给谁（保险公司 / 修理厂）
    description     TEXT,                           -- 用途说明
    occurred_date   DATE,                           -- 发生日期，备查用
    remarks         TEXT,
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,
    created_by      INTEGER REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE contract_additional_items IS '合同附加项（应收清单上的额外项目）';
COMMENT ON COLUMN contract_additional_items.paid_to IS '付给谁（保险公司/修理厂），用于对账';

-- 软删过滤的部分索引：列表查询 contract 的附加项时只命中未删除行
CREATE INDEX IF NOT EXISTS idx_addl_items_contract
    ON contract_additional_items(contract_id) WHERE is_deleted = FALSE;


-- 2. contracts 表扩展：附加项按币种汇总冗余字段
ALTER TABLE contracts
    ADD COLUMN IF NOT EXISTS additional_total_by_currency JSONB
        NOT NULL DEFAULT '{}'::jsonb;
COMMENT ON COLUMN contracts.additional_total_by_currency
    IS '附加项按币种汇总，例 {"CNY": 20000, "HKD": 500}；由 AdditionalItemService 增删改时同步维护';


-- 3. payments 表扩展：附加项标签（可选，仅展示用，不参与金额聚合）
ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS additional_item_id INTEGER
        REFERENCES contract_additional_items(id) ON DELETE SET NULL;
COMMENT ON COLUMN payments.additional_item_id
    IS '附加项标签（可选）：记录这笔付款主要是为某项附加项；不影响金额聚合';
-- 标签反查索引（仅命中打标行）
CREATE INDEX IF NOT EXISTS idx_payments_addl_item
    ON payments(additional_item_id) WHERE additional_item_id IS NOT NULL;


-- 4. contracts 表扩展：附加项折算到合同主币种的总额（应收口径统一用）
--    与 paid_amount 同币种口径，使「应收 = 合同金额 + 附加项」可直接与已收比较。
--    NULL 表示未折算（缺汇率或合同从未维护过附加项），前端降级用 total_amount。
ALTER TABLE contracts
    ADD COLUMN IF NOT EXISTS additional_total_in_contract_currency DECIMAL(15,2);
COMMENT ON COLUMN contracts.additional_total_in_contract_currency
    IS '附加项折算到合同主币种的总额（与 paid_amount 同口径，用于应收口径统一）；缺汇率或未维护时为 NULL，由 AdditionalItemService 增删改时同步维护';
