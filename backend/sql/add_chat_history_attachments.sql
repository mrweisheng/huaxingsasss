-- 给 chat_history 表加 attachments 列，用于持久化用户消息附件元信息
-- 历史回看时能看到「当时上传了什么文件」(file_id / file_type / file_name)
-- 文件本身仍存放在 TEMP_UPLOAD_DIR；如附件已被启动清理，回看时可能 404，按需求阶段 B 再处理

ALTER TABLE chat_history
ADD COLUMN IF NOT EXISTS attachments JSONB;

COMMENT ON COLUMN chat_history.attachments IS '用户消息附件列表 [{file_id, file_type, file_name}]';
