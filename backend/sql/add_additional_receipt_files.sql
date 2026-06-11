-- 支持一笔付款关联多张凭证：主凭证存 receipt_image_path，其余存 additional_receipt_files
ALTER TABLE payments ADD COLUMN IF NOT EXISTS additional_receipt_files JSON;
COMMENT ON COLUMN payments.additional_receipt_files IS '补充凭证文件列表 [{file_path, file_hash, receipt_data}]';
