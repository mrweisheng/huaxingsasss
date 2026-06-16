-- 补充：现金收款渠道
-- 收款除银行/支付宝/微信等账户外，还可能收取现金。现金无具体账户信息（户名/卡号），
-- 作为一种"收款渠道"存入 payment_accounts，使表单收款账户下拉统一，前后端无需特殊判断。
-- 可重复执行（WHERE NOT EXISTS 防重复）。
INSERT INTO payment_accounts (account_type, title, account_name, is_default, sort_order)
SELECT 'cash', '现金', '现金', FALSE, 99
WHERE NOT EXISTS (
    SELECT 1 FROM payment_accounts WHERE account_type = 'cash' AND title = '现金' AND is_deleted = FALSE
);
