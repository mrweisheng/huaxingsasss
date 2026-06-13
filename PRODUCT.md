# 华星 SASS 系统产品文档

## 1. 产品概述

华星 SASS 系统是一个面向汽车贸易公司的业务管理平台，专注于**车辆买卖**和**两地牌过户**两大核心业务。系统整合了合同管理、客户管理、财务收付款、智能 AI 助手等功能，旨在提升业务处理效率和财务透明度。

### 1.1 核心价值

- **智能化合同处理**：通过 AI 自动解析合同文件（PDF/图片），提取关键信息
- **全链路财务管理**：支持多币种（CNY/HKD）收付款记录，自动汇率换算
- **业务可视化**：财务总览仪表盘，实时掌握经营状况
- **AI 助手**：自然语言交互，快速完成业务操作

---

## 2. 业务类型

### 2.1 车辆买卖

- **业务描述**：二手车/新车买卖交易
- **业务色**：钢蓝 `#2d5b8a`
- **典型场景**：购买现牌车辆、新车订购

### 2.2 两地牌过户

- **业务描述**：中港两地车牌过户业务
- **业务色**：朱砂 `#b8423b`
- **典型场景**：粤港两地牌车辆转让

### 2.3 其他业务类型

- 年检保险
- 其他

---

## 3. 用户角色与权限

### 3.1 角色定义

| 角色 | 代码 | 权限说明 |
|------|------|----------|
| **管理员** | `admin` | 全系统管理权限，可查看所有数据、删除记录、管理用户 |
| **收入专员** | `income` | 负责合同创建、收款录入，仅能查看自己负责的合同和收入 |
| **支出专员** | `expense` | 负责支出录入，仅能查看自己创建的支出记录 |

### 3.2 权限矩阵

| 功能模块 | admin | income | expense |
|----------|-------|--------|---------|
| 客户管理 | ✅ 全部 | ✅ 自己创建的 | ❌ 无权查看 |
| 合同管理 | ✅ 全部 | ✅ 自己负责的 | ❌ 只读（无修改权） |
| 收入录入 | ✅ 全部 | ✅ 仅自己合同 | ❌ 无权 |
| 支出录入 | ✅ 全部 | ❌ 无权 | ✅ 自己创建的 |
| 财务总览 | ✅ 全量数据 | ❌ 无权访问 | ❌ 无权访问 |
| 用户管理 | ✅ 全部 | ❌ 无权 | ❌ 无权 |
| 合同删除 | ✅ 仅管理员 | ❌ 无权 | ❌ 无权 |
| 付款删除 | ✅ 仅管理员 | ❌ 无权 | ❌ 无权 |

---

## 4. 核心功能模块

### 4.1 客户管理

#### 功能说明

- **客户创建**：录入客户基本信息（姓名、电话、邮箱、身份证号等）
- **客户去重**：同名+同电话 或 同名+同邮箱 视为同一客户，自动合并补充信息
- **客户搜索**：支持姓名（繁简兼容）、电话、邮箱、微信群名模糊搜索
- **客户详情**：查看客户基本信息及关联合同列表

#### 数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 客户名称（必填） |
| contact_person | string | 联系人 |
| phone | string | 联系电话 |
| email | string | 联系邮箱 |
| id_card_number | string | 身份证号（base64 编码存储） |
| business_license | string | 营业执照号 |
| address | string | 地址 |
| wechat_group_name | string | 微信群名称 |
| remarks | string | 备注 |

#### ⚠️ 存疑点

1. **身份证号加密方案**：当前使用 base64 编码（可逆），非真正加密。生产环境建议升级为 AES-GCM + KMS 密钥管理
2. **客户删除策略**：当前为硬删除，仅允许无活跃合同时删除。是否需要软删除保留历史记录？

---

### 4.2 合同管理

#### 功能说明

- **合同创建**：支持手动创建和 AI 智能解析创建
- **合同状态**：draft（草稿）→ active（执行中）→ completed（已完成）
- **合同文件**：存储原始合同文件，支持在线预览/下载
- **AI 解析**：自动提取合同关键信息（金额、日期、业务类型等）
- **合同搜索**：支持合同编号、标题、客户名称、业务类型等多维度搜索

#### 数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| contract_number | string | 合同编号（自动生成：HT+时间戳+随机码） |
| title | string | 合同标题 |
| business_type | string | 业务类型：车辆买卖/两地牌过户/年检保险/其他 |
| business_description | string | 业务描述 |
| customer_id | int | 关联客户 ID |
| sales_person_id | int | 业务员 ID |
| currency | string | 币种：CNY/HKD |
| total_amount | decimal | 合同总金额 |
| paid_amount | decimal | 已付金额 |
| remaining_amount | decimal | 剩余金额 |
| total_amount_in_cny | decimal | 合同总额折算 CNY |
| paid_amount_in_cny | decimal | 已付金额折算 CNY |
| remaining_amount_in_cny | decimal | 剩余金额折算 CNY |
| total_expense | decimal | 总支出金额 |
| total_expense_in_cny | decimal | 总支出折算 CNY |
| original_file_path | string | 原始合同文件路径 |
| file_hash | string | 文件 SHA256 哈希 |
| contract_data | jsonb | AI 解析的结构化数据 |
| contract_text | text | 合同全文内容 |
| confidence | decimal | AI 解析置信度 |
| needs_review | boolean | 是否需要人工审核 |
| wechat_group | string | 业务微信群名称 |
| status | string | 状态：draft/pending_review/active/completed/cancelled/disputed |
| signed_date | date | 签订日期 |
| start_date | date | 生效日期 |
| end_date | date | 到期日期 |
| remarks | string | 备注 |

#### 合同状态流转

```
draft（草稿）
    ↓
active（执行中）← AI 解析完成或手动确认
    ↓
completed（已完成）← 管理员手动标记
```

#### ⚠️ 存疑点

1. **合同状态机**：当前只有 draft → active → completed 三态，是否需要增加 cancelled（取消）、disputed（争议）等状态？
2. **合同删除逻辑**：当前为硬删除，仅允许无付款记录时删除。是否需要软删除？
3. **AI 解析置信度**：置信度 < 0.85 时标记 needs_review，但当前流程中没有强制人工审核环节

---

### 4.3 付款管理

#### 功能说明

- **收入录入**：记录客户付款（定金、尾款等）
- **支出录入**：记录业务支出（保险费、过户费等）
- **凭证管理**：上传付款凭证（银行转账截图、微信/支付宝截图等）
- **凭证识别**：AI 自动识别凭证信息（金额、时间、付款方等）
- **多币种支持**：支持 CNY/HKD，自动汇率换算
- **状态管理**：pending（待确认）→ paid（已确认）

#### 数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| contract_id | int | 关联合同 ID |
| installment_number | int | 第几期 |
| installment_name | string | 期数名称（如"定金"、"尾款"） |
| type | string | 类型：income（收入）/ expense（支出） |
| currency | string | 币种：CNY/HKD |
| amount | decimal | 本期应付金额 |
| paid_amount | decimal | 实际已付金额 |
| exchange_rate | decimal | 使用的汇率 |
| amount_in_cny | decimal | 折算 CNY 金额 |
| paid_amount_in_cny | decimal | 已付折算 CNY |
| due_date | date | 应付款日期 |
| paid_date | date | 实际付款日期 |
| receipt_image_path | string | 付款凭证图片路径 |
| receipt_file_hash | string | 凭证文件哈希 |
| receipt_ocr_text | string | OCR 识别的文本内容 |
| receipt_data | json | 凭证分析结构化数据 |
| additional_receipt_files | json | 补充凭证文件列表 |
| payment_method | string | 付款方式：bank_transfer/wechat/alipay/cash/check |
| payee_name | string | 收款方名称（仅支出使用） |
| status | string | 状态：pending（待确认）/ paid（已确认） |
| source | string | 来源：manual（手动）/ screenshot（截图）/ upload（上传） |
| notes | string | 备注 |
| description | string | 自动生成的可读描述 |

#### 付款状态流转

```
创建付款记录
    ↓
pending（无凭证时）
    ↓
paid（补充凭证后自动转换）← 凭证确认参与结算
```

#### ⚠️ 存疑点

1. **付款删除逻辑**：当前为硬删除，删除后会反写合同金额。是否需要软删除保留审计记录？
2. **凭证文件清理**：删除付款记录时会删除物理凭证文件，是否需要归档？
3. **多张凭证合并**：当前支持多张凭证合并录入，但前端交互是否清晰？

---

### 4.4 财务总览

#### 功能说明

- **核心 KPI**：合同数、客户数、已收金额、待收金额、支出金额、利润
- **每日业务趋势**：近 30 天成交合同数和客户数趋势图
- **月度收款趋势**：近 30 天按币种分的收款趋势图

#### 数据口径

- **已收金额**：从 contracts 表汇总 paid_amount（按币种分）
- **待收金额**：从 contracts 表汇总 remaining_amount（按币种分）
- **支出金额**：从 contracts 表汇总 total_expense（按币种分）
- **利润**：已收金额 - 支出金额

#### ⚠️ 存疑点

1. **利润计算口径**：当前利润 = 已收 - 支出，是否需要考虑成本、税费等其他因素？
2. **趋势图时间范围**：固定近 30 天，是否需要支持自定义时间范围？

---

### 4.5 AI 智能助手（小星助手）

#### 功能说明

- **自然语言交互**：通过对话方式完成业务操作
- **文件分析**：上传合同/凭证文件，AI 自动识别和提取信息
- **智能录入**：根据对话内容自动填充表单
- **多工具协同**：14 个工具覆盖查询、创建、更新等操作

#### 支持的工具

| 工具名 | 类型 | 说明 |
|--------|------|------|
| analyze_files | 分析 | 统一文件分析（合同/凭证/群聊） |
| get_overview | 查询 | 系统全局统计概览 |
| search_customers | 查询 | 搜索客户（模糊匹配，兼容繁简） |
| create_customer | 写入 | 创建客户（同名去重） |
| update_customer | 写入 | 更新客户信息 |
| search_contracts | 查询 | 搜索合同 |
| get_contract_detail | 查询 | 合同详情 + 付款记录 |
| create_contract | 写入 | 创建合同（自动关联文件分析结果） |
| update_contract | 写入 | 更新合同元信息 |
| query_payments | 查询 | 付款记录查询 |
| create_payment_record | 写入 | 统一收入/支出创建 |
| match_and_confirm_payment | 写入 | 凭证录入收款记录 |
| update_payment | 写入 | 更新付款记录 |
| search_contract_text | 查询 | 合同全文搜索 |

#### 交互流程

```
用户发送消息/上传文件
    ↓
AI 分析意图，决定调用工具
    ↓
执行工具，返回结果
    ↓
AI 整理结果，回复用户
```

#### ⚠️ 存疑点

1. **工具执行权限**：当前所有工具对所有用户开放，是否需要按角色限制？
2. **写入确认机制**：写入操作由 LLM 自主判断是否需要确认，是否需要强制确认？
3. **文件存储策略**：agent_upload 目录下的临时文件是否需要定期清理？

---

### 4.6 用户管理

#### 功能说明

- **用户创建**：管理员创建新用户账号
- **角色分配**：设置用户角色（admin/income/expense）
- **状态管理**：启用/禁用用户账号

#### 数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| username | string | 用户名（唯一） |
| password_hash | string | 密码哈希 |
| email | string | 邮箱（唯一） |
| full_name | string | 真实姓名 |
| role | string | 角色：admin/income/expense |
| department | string | 部门 |
| is_active | boolean | 是否激活 |
| last_login_at | datetime | 最后登录时间 |

---

### 4.7 汇率管理

#### 功能说明

- **汇率查询**：查询指定日期的汇率
- **汇率获取**：自动从外部 API 获取实时汇率
- **汇率存储**：历史汇率存入数据库，支持 30 天内最近匹配

#### 汇率来源优先级

1. 数据库精确日期匹配
2. API 自动获取（frankfurter.dev → open.er-api.com）
3. 数据库 30 天内最近汇率
4. 系统默认汇率（HKD/CNY: 0.92）

#### ⚠️ 存疑点

1. **汇率 API 可靠性**：外部 API 可能不稳定，是否需要备用数据源？
2. **汇率更新频率**：当前按需获取，是否需要定时更新？

---

## 5. 数据模型关系

```
┌─────────────┐
│   users     │
└──────┬──────┘
       │ created_by / sales_person_id
       ↓
┌─────────────┐     ┌─────────────┐
│  customers  │←────│  contracts  │
└─────────────┘     └──────┬──────┘
                           │ contract_id
                           ↓
                    ┌─────────────┐
                    │  payments   │
                    └─────────────┘

┌─────────────┐
│exchange_rate│
└─────────────┘

┌─────────────┐
│    files    │
└─────────────┘

┌─────────────┐
│ audit_log   │
└─────────────┘

┌─────────────┐
│chat_session │
└──────┬──────┘
       │ session_id
       ↓
┌─────────────┐
│chat_history │
└─────────────┘

┌─────────────┐
│ agent_file  │
└─────────────┘
```

---

## 6. API 接口概览

### 6.1 认证接口

- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/logout` - 用户登出
- `GET /api/v1/auth/me` - 获取当前用户信息

### 6.2 客户接口

- `GET /api/v1/customers` - 获取客户列表
- `GET /api/v1/customers/{id}` - 获取客户详情
- `POST /api/v1/customers` - 创建客户
- `PUT /api/v1/customers/{id}` - 更新客户
- `DELETE /api/v1/customers/{id}` - 删除客户

### 6.3 合同接口

- `GET /api/v1/contracts` - 获取合同列表
- `GET /api/v1/contracts/{id}` - 获取合同详情
- `POST /api/v1/contracts` - 创建合同
- `PUT /api/v1/contracts/{id}` - 更新合同
- `DELETE /api/v1/contracts/{id}` - 删除合同
- `GET /api/v1/contracts/{id}/file` - 下载合同文件
- `POST /api/v1/contracts/{id}/complete` - 标记合同完成
- `POST /api/v1/contracts/{id}/confirm-parsed-data` - 确认 AI 解析结果

### 6.4 付款接口

- `GET /api/v1/payments` - 获取付款列表
- `GET /api/v1/payments/contract/{contract_id}` - 获取合同付款记录
- `POST /api/v1/payments` - 创建付款记录
- `PUT /api/v1/payments/{id}` - 更新付款记录
- `DELETE /api/v1/payments/{id}` - 删除付款记录
- `GET /api/v1/payments/{id}/receipt` - 查看付款凭证

### 6.5 统计接口

- `GET /api/v1/stats/financial-overview` - 获取财务总览

### 6.6 文件接口

- `POST /api/v1/files/upload` - 上传文件
- `GET /api/v1/files/{file_id}` - 获取文件

### 6.7 Agent 接口

- `POST /api/v1/agent/chat` - AI 对话（SSE 流式响应）
- `POST /api/v1/agent/upload` - 上传文件到 Agent
- `GET /api/v1/agent/sessions` - 获取会话列表
- `POST /api/v1/agent/sessions` - 创建会话
- `DELETE /api/v1/agent/sessions/{session_id}` - 删除会话
- `GET /api/v1/agent/history/{session_id}` - 获取会话历史

---

## 7. 前端页面结构

### 7.1 页面路由

| 路由 | 页面 | 权限 |
|------|------|------|
| `/login` | 登录页 | 公开 |
| `/agent` | AI 助手（小星助手） | 所有角色 |
| `/customers` | 客户列表 | admin/income |
| `/customers/:id` | 客户详情 | admin/income |
| `/contracts` | 合同列表 | admin/income |
| `/contracts/:id` | 合同详情 | 所有角色（有权限检查） |
| `/payments` | 付款列表 | 所有角色 |
| `/financial-overview` | 财务总览 | admin |
| `/users` | 用户管理 | admin |

### 7.2 默认首页

- 登录后默认进入 `/agent`（AI 助手页面）

---

## 8. 设计系统

### 8.1 业务色

| 业务 | 主色 | 深色 | 浅底 | 极浅底 |
|------|------|------|------|--------|
| 车辆业务 | `#2d5b8a` 钢蓝 | `#1e3f63` | `#e5edf6` | `#f4f7fb` |
| 两地牌过户 | `#b8423b` 朱砂 | `#8f2d28` | `#fbe9e7` | `#fdf4f3` |

### 8.2 状态色

| 状态 | 色值 | 用途 |
|------|------|------|
| 已收/落袋 | `#c9952b` 金 | 已收金额、paid 状态 |
| 全额结清 | `#0d9488` teal | 100% 回款 |
| 未收/警示 | `#dc6b3d` 暖橙 | 未收金额、逾期 |
| 录入收入 | `#5b8c63` 鼠尾草绿 | 收入侧操作专色 |

### 8.3 品牌色

- `--brand-primary #1e3a5f` 深蓝：侧边栏、主按钮、页头
- `--brand-gold #c9952b` 金色：金额数字、强调元素

---

## 9. 技术架构

### 9.1 技术栈

- **后端**：FastAPI · SQLAlchemy 2.x · Pydantic v2 · PostgreSQL
- **前端**：Vite · React · TypeScript · Zustand · Ant Design
- **AI**：LangGraph · LLM（百炼 + SiliconFlow）
- **文件存储**：本地文件系统
- **数据库**：PostgreSQL

### 9.2 核心模块

| 模块 | 文件 | 说明 |
|------|------|------|
| Agent 图 | `app/ai/orchestrator/unified_agent.py` | 单层循环架构 |
| 工具执行 | `app/ai/tool_executor.py` | 14 个工具定义 |
| 提示词 | `app/ai/prompts.py` | 业务规则和追问策略 |
| LLM 客户端 | `app/ai/llm_client.py` | 统一 LLM 入口 |
| 业务 Service | `app/services/*.py` | 业务规则、权限校验 |
| 权限 | `app/core/permissions.py` | 角色和权限判断 |

---

## 10. 部署与配置

### 10.1 环境变量

| 变量 | 说明 |
|------|------|
| DATABASE_URL | 数据库连接串 |
| JWT_SECRET_KEY | JWT 密钥 |
| LLM_API_KEY | LLM API 密钥 |
| LANGCHAIN_TRACING_V2 | LangSmith 追踪开关 |

### 10.2 启动命令

```bash
# 后端
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend && npm run dev
```

---

## 11. 已知问题与待确认项

### 11.1 安全相关

| 问题 | 严重程度 | 说明 |
|------|----------|------|
| 身份证号 base64 编码 | 中 | 当前可逆，建议升级为 AES-GCM 加密 |
| 软删除缺失 | 低 | 客户/合同/付款均为硬删除，历史数据不可恢复 |

### 11.2 业务逻辑

| 问题 | 严重程度 | 说明 |
|------|----------|------|
| 合同状态机不完整 | 中 | 缺少 cancelled/disputed 状态 |
| 利润计算口径 | 低 | 当前 = 已收 - 支出，是否需要考虑其他成本？ |
| AI 解析审核流程 | 中 | needs_review 标记后无强制审核环节 |

### 11.3 功能完整性

| 问题 | 严重程度 | 说明 |
|------|----------|------|
| 密码修改功能 | 低 | 当前无用户自助修改密码入口 |
| 数据导出 | 低 | 无批量导出功能（仅有合同台账导出） |
| 操作日志查看 | 低 | 审计日志存在但无前端展示页面 |

---

## 12. 附录

### 12.1 合同编号规则

格式：`HT` + `YYYYMMDDHHMMSS` + 4位随机码

示例：`HT20260613143052A1B2`

### 12.2 文件存储路径

- 合同文件：`{CONTRACT_UPLOAD_DIR}/{original_file_path}`
- 凭证文件：`{RECEIPT_UPLOAD_DIR}/{receipt_image_path}`
- Agent 上传：`{CONTRACT_UPLOAD_DIR}/agent_upload/{file_id}`

### 12.3 汇率计算

- 同币种：汇率 1:1
- 非同币种：通过 CNY 交叉汇率计算
  - HKD → CNY：HKD 金额 × HKD/CNY 汇率
  - CNY → HKD：CNY 金额 ÷ HKD/CNY 汇率

---

*文档生成时间：2026-06-13*
*文档版本：v1.0*
