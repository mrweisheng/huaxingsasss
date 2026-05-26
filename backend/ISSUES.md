# 已知问题与待办事项

## 测试套件已知问题

### 1. bcrypt 5.0 与 passlib 不兼容
- **现象**: `ValueError: password cannot be longer than 72 bytes`
- **原因**: passlib 1.7.4 与 bcrypt 5.0+ 存在兼容性问题，passlib 内部检测 bcrypt 版本时使用了一个已知会触发此错误的测试密码
- **修复方案**: `pip install 'bcrypt<5.0.0'` 降级 bcrypt 到 4.x 版本
- **影响**: 仅影响测试环境，生产环境需确保 bcrypt 版本锁定
- **pyproject.toml 建议**: 添加 `bcrypt = ">=4.0,<5.0"` 约束

### 2. PostgreSQL INET 类型不可用于 SQLite 测试
- **已修复**: `app/models/audit_log.py` 的 `ip_address` 字段从 `INET` 改为 `String(45)`
- **原因**: SQLite 不支持 PostgreSQL 的 INET 类型，导致 `Base.metadata.create_all()` 失败
- **注意**: 迁移文件 `20260525_001_initial_schema.py` 仍使用 `postgresql.INET()`，生产环境不受影响

### 3. JSONB 类型不可用于 SQLite 测试
- **已修复**: 以下模型的 JSONB 字段改为通用 JSON 类型：
  - `app/models/contract.py` — `contract_data`
  - `app/models/audit_log.py` — `old_values`, `new_values`
  - `app/models/file.py` — `ai_extracted_data`
  - `app/models/chat_history.py` — `extracted_entities`
- **影响**: SQLAlchemy 的 JSON 类型在 PostgreSQL 下自动映射为 JSONB 存储，性能无差异
- **迁移文件**: 生产迁移仍使用 `postgresql.JSONB`，不受影响

## 待完成优化项

### 高优先级
- [ ] 前端竞态条件修复（AbortController）
- [ ] 前端 SSE 连接清理
- [ ] 前端 Token 刷新防循环
- [ ] 前端 PaymentList 类型安全

### 中优先级
- [ ] 测试套件通过（需解决 bcrypt 版本问题）

### 低优先级
- [ ] `on_event` 弃用警告 → 改用 lifespan 事件处理器
- [ ] Pydantic v2 `class Config` 弃用警告 → 改用 `model_config = ConfigDict(...)`
- [ ] Celery worker 的健康检查与重启策略
- [ ] Redis 连接池配置优化
