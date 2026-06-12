-- 创建 agent_file 表，用于持久化 Agent 附件文件元数据（与会话脱钩，上传时就落表）
-- 执行后需要 pm2 restart 后端
-- 新增配置项在 .env 中：AGENT_FILE_DIR（默认 /data/contract-system/agent-files）

CREATE TABLE IF NOT EXISTS agent_file (
    id            SERIAL PRIMARY KEY,
    file_id       VARCHAR(64)  NOT NULL UNIQUE,
    user_id       INTEGER      NOT NULL REFERENCES users(id),
    session_id    VARCHAR(100),
    original_name TEXT,
    mime_type     VARCHAR(120),
    file_size     INTEGER,
    storage_path  TEXT         NOT NULL,
    file_type     VARCHAR(20),
    created_at    TIMESTAMPTZ  DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  DEFAULT NOW(),
    is_deleted    BOOLEAN      DEFAULT FALSE,
    deleted_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_file_file_id   ON agent_file(file_id);
CREATE INDEX IF NOT EXISTS idx_agent_file_user_id   ON agent_file(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_file_session   ON agent_file(session_id);

COMMENT ON TABLE  agent_file                   IS 'Agent 上传的持久化附件元信息';
COMMENT ON COLUMN agent_file.file_id           IS 'UUID，对外引用标识';
COMMENT ON COLUMN agent_file.user_id           IS '上传者（鉴权用）';
COMMENT ON COLUMN agent_file.session_id        IS '关联会话 ID，finalize 时回填';
COMMENT ON COLUMN agent_file.original_name     IS '原始文件名';
COMMENT ON COLUMN agent_file.mime_type         IS 'MIME 类型';
COMMENT ON COLUMN agent_file.file_size         IS '字节大小';
COMMENT ON COLUMN agent_file.storage_path      IS '相对 AGENT_FILE_DIR 的路径';
COMMENT ON COLUMN agent_file.file_type         IS '分类：image / pdf / word / excel / text';