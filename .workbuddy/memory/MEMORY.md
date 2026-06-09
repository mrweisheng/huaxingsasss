# 项目架构记忆

## 智能体架构重构（2026-06-08）

### 决策记录
- 采用激进重构方案，不缝补旧架构
- 单层 Agent 循环替代 Root Graph + 3 子图
- 废弃 set_pending_plan，改轻量确认机制
- 工具集从 20 个精简到 14 个
- ContractAnalyzer + ReceiptAnalyzer 合并为 FileAnalyzer
- 新增 analyze_files 工具让 LLM 主动调度文件分析
- 详细方案见 AGENT_REFACTOR_PLAN.md

### 关键设计原则
- 让 LLM 做它擅长的（理解意图、看图、决策）
- 让代码做代码擅长的（文件分析、数据匹配、事务保障）
- 不用代码猜 LLM 想干什么，而是给 LLM 工具让它告诉代码它想干什么

### 业务核心流程
1. 录入合同 → 自动创建 pending 收款记录
2. 录入凭证 → 智能匹配已有 pending 记录 → 确认 → paid
3. 录入支出 → 上传凭证 → 创建支出记录
4. 所有录入操作需要有凭证才能确认
