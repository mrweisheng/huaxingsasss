-- 新建 chat_sessions 表：存储会话元数据（mode、context）
-- 现有 session 仅靠 chat_history.session_id 虚拟分组，缺少 mode/context 等元数据

CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL UNIQUE,    -- UUID，与 chat_history.session_id 对应
    user_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(200),
    mode VARCHAR(20) NOT NULL DEFAULT 'chat',  -- chat | receipt_income | receipt_expense
    context JSONB DEFAULT NULL,                -- {"contract_id": 123, "payment_type": "income"}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_session_id ON chat_sessions(session_id);
