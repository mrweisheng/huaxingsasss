# CLAUDE.md

## Agent 模式（任何涉及 LLM 的流程必须遵守）

**正确 — LLM 决策循环：**
```
工具返回结果 → LLM 看结果 → LLM 决定下一步（调哪个工具 / 问用户 / 结束）
```

**错误 — 硬编码流水线：**
```
工具返回结果 → 代码 if/else 决定下一步 → LLM 没有选择权
```

**判断标准：** 找到每一个决定"下一步做什么"的 if/else。这个 if 是你写的还是 LLM 在运行时做的？你写的 = 流水线，LLM 做的 = Agent。

工具依赖不是流水线——图片必须先 analyze 才能理解，这是工具能力约束。但 analyze 之后代码自动调 create_contract，这是流水线——应该由 LLM 看了结果后决定。

**工具铁律：** 工具只返回事实 JSON，不嵌入"建议下一步""请先..."等行为指令。

## 硬规则
- 禁止创建 alembic 迁移脚本，DDL 以纯 SQL 提供
- 禁止修改已上线接口的响应格式
- 数据库操作只走 Service 层，路由层不操作 ORM

## 技术锚点
- uv（后端）/ npm（前端）· FastAPI + SQLAlchemy + Pydantic v2
- LangGraph 编排 / legacy ReAct 回滚
- LLM 客户端见 backend/app/ai/llm_client.py

## 命令
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd backend && uv run pytest
cd frontend && npm run dev
