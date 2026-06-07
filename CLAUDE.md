# CLAUDE.md

## Agent 模式（最高优先级）

**判断标准：找到每一个决定"下一步做什么"的 if/else。**
**这个 if 是你写的 = 流水线，LLM 运行时做的 = Agent。**

```
正确：工具返回结果 → LLM 看结果 → LLM 决定下一步（调哪个工具 / 问用户 / 结束）
错误：工具返回结果 → 代码 if/else 决定下一步 → LLM 没有选择权
```

**修改或新增任何业务逻辑前，先回答 3 个问题：**

1. **这是流水线场景还是 agent 场景？**
   - 流水线（纯 CRUD、Service 层、确定规则的表单操作）→ 走既有分层，代码直接执行
   - agent（自然语言理解、多步推理、工具组合）→ LLM 决策，代码只做执行
2. **业务规则放哪一层？**
   - 数据完整性 / 安全边界 / 权限 → 工具层 / Service 层硬编码
   - 业务偏好 / 展示风格 / 追问策略 → system prompt 软规则
   - 工具能力约束（如图片必须先识别）→ 写在工具描述或节点逻辑里
3. **我是不是在用 if/else 偷懒代替 LLM 决策？**
   - 如果是 → 改成让 LLM 看上下文自己判断

**工具铁律：** 工具只返回事实 JSON，不嵌入"建议下一步""请先..."等行为指令。

**不适用本规则的范围：** 纯表单 CRUD、标准 REST 增删改查、Service 层业务封装、纯查询接口——这些是流水线，按既有规范写即可。

## 硬规则

- 禁止创建 alembic 迁移脚本，DDL 以纯 SQL 提供
- 禁止修改已上线接口的响应格式
- 数据库操作只走 Service 层，路由层不操作 ORM
- 禁止把 agent 能做的判断用 Python if/else 硬编码实现（除非属于"工具能力约束"或"数据完整性"边界）

## 技术锚点

- uv（后端）/ npm（前端）· FastAPI + SQLAlchemy + Pydantic v2
- LangGraph 编排 · StateGraph / interrupt / checkpoint / 子图
- LLM 客户端见 backend/app/ai/llm_client.py

## 命令

```bash
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd backend && uv run pytest
cd frontend && npm run dev
cd frontend && npx tsc --noEmit
```
