"""LangGraph 编排层 v2

单层 Agent 循环架构（unified_agent.py），替代旧的 Root Graph + 4 子图。

文件说明：
  - unified_agent.py  — 统一 Agent 图（call_model ↔ execute_tool → finalize）
  - state_v2.py       — 精简 AgentState（9 字段）
  - sse_adapter.py     — SSE 事件适配器
  - checkpointer.py    — AsyncPostgresSaver 工厂

设计文档：AGENT_REFACTOR_PLAN.md (项目根目录)
"""
