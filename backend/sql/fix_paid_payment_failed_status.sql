-- 修复历史脏数据：status=paid 但 verification_status=failed 的非法状态组合
--
-- 背景：
--   create_payment_with_override 此前对 income 放行写入 status=paid + verification_status=failed，
--   违反状态机语义（paid 记录的 verification_status 只能是 passed；failed 仅用于 pending 待放行）。
--   该 bug 已在 payment_service.py 修正（放行 → passed）。
--
-- 本脚本修正存量脏数据：所有 paid 且 failed 的记录，统一改为 passed。
-- 这些记录的 verification_result 里已带 manual_override=true 印记，审计追溯信息不丢失。
--
-- 执行前可先 SELECT 预览影响范围：
--   SELECT id, contract_id, type, status, verification_status, verification_result->>'manual_override'
--   FROM payments
--   WHERE status = 'paid' AND verification_status = 'failed' AND is_deleted = false;

UPDATE payments
SET verification_status = 'passed',
    updated_at = NOW()
WHERE status = 'paid'
  AND verification_status = 'failed'
  AND is_deleted = false;
