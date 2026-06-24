-- 合同表：为 wechat_group 加索引
-- 背景：业务微信群名称现升级为必填字段，且是业务员查找合同的主要线索
-- （"查这个群0605深圳湾新办理"）。加索引提升按群名查询的性能。
-- 群名允许重复（不同客户/不同业务可能同名），故仅建普通索引，不加 unique。
-- 可重复执行（IF NOT EXISTS 防重复）。

CREATE INDEX IF NOT EXISTS idx_contracts_wechat_group
    ON contracts (wechat_group);

COMMENT ON COLUMN contracts.wechat_group IS '业务微信群名称（必填：每笔业务都关联一个业务群）';
