-- 合同表：为 wechat_group 加索引
-- 背景：业务微信群名称现升级为必填字段，且是业务员查找合同的主要线索
-- （"查这个群0605深圳湾新办理"）。加索引提升按群名查询的性能。
-- 群名允许重复（不同客户/不同业务可能同名），故仅建普通索引，不加 unique。
-- 可重复执行（IF NOT EXISTS 防重复）。
--
-- 历史：早期 app/models/contract.py 同时用 `index=True` 声明，导致同一列存在两个不同名索引
-- （ix_contracts_wechat_group + idx_contracts_wechat_group）。按 CLAUDE.md「无 alembic、
-- DDL 走 SQL」原则，索引统一由 SQL 脚本管理，本脚本负责：
--   1. 删除 model 自动建的冗余索引（若存在）
--   2. 创建 SQL 脚本管理的标准索引

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'contracts'
          AND indexname = 'ix_contracts_wechat_group'
    ) THEN
        DROP INDEX ix_contracts_wechat_group;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_contracts_wechat_group
    ON contracts (wechat_group);

COMMENT ON COLUMN contracts.wechat_group IS '业务微信群名称（必填：每笔业务都关联一个业务群）';