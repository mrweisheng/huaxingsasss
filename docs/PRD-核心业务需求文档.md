# 华星资源管理系统 — 核心业务需求文档

> **编写原则**：本文档严格基于项目实际代码（`D:\CODE PROJECT\huaxingsasss`），不做任何偏离或臆测。
>
> **代码版本**：2026-06-06 | **技术栈**：FastAPI (Python) + React (TypeScript) + PostgreSQL 17
>
> **审查状态**：✅ 已通过严格代码对照审查

---

## 目录

1. [系统概述](#1-系统概述)
2. [核心业务一：合同创建](#2-核心业务一合同创建)
3. [核心业务二：自动创建与关联客户](#3-核心业务二自动创建与关联客户)
4. [核心业务三：合同收入与支出录入](#4-核心业务三合同收入与支出录入)
5. [角色权限模型](#5-角色权限模型)
6. [核心数据模型关系图](#6-核心数据模型关系图)
7. [核心业务数据流](#7-核心业务数据流)

---

## 1. 系统概述

### 1.1 项目定位

华星资源管理系统是为「华星资源开发有限公司」打造的企业级合同管理与财务收付系统。核心业务围绕**中港两地车牌指标过户服务**展开，支持多币种（CNY/HKD/USD）合同管理、AI 驱动的合同文件智能解析，以及收入/支出的精细化跟踪。

### 1.2 技术架构

| 层级 | 技术选型 | 关键文件 |
|------|---------|---------|
| 后端框架 | FastAPI (Python) | `backend/app/main.py` |
| ORM | SQLAlchemy | `backend/app/models/` |
| 数据库 | PostgreSQL 17 | `public.sql` |
| 前端框架 | React 18 + TypeScript | `frontend/src/` |
| 构建工具 | Vite | `frontend/vite.config.ts` |
| UI 组件库 | Ant Design 5 | `frontend/package.json` |
| 认证方案 | JWT 双 Token (access 15min + refresh 7天) | `backend/app/core/security.py` |
| 状态管理 | Zustand | `frontend/src/store/useAuthStore.ts` |

### 1.3 核心业务域

```
┌─────────────────────────────────────────────────┐
│                  华星资源管理系统                  │
│                                                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐  │
│  │  客户管理  │   │  合同管理  │   │  收付管理     │  │
│  │ Customer │◄──│ Contract │──►│   Payment    │  │
│  └──────────┘   └──────────┘   └──────────────┘  │
│       ▲              ▲                ▲           │
│       │              │                │           │
│       └──────────────┴────────────────┘           │
│                  用户体系 (User)                   │
│            admin / income / expense               │
└─────────────────────────────────────────────────┘
```

---

## 2. 核心业务一：合同创建

### 2.1 数据库模型

**表名**：`contracts` | **模型文件**：`backend/app/models/contract.py`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | Integer (PK) | 是 | 自增主键 |
| `contract_number` | String(50) | 是 | **唯一**合同编号，格式 `HT{YYYYMMDDHHmmss}{4位随机hex}` |
| `title` | String(500) | 否 | 合同标题（初始=上传文件名） |
| `business_type` | String(50) | 否 | 业务类型：`车辆买卖`/`两地牌过户`/`年检保险`/`其他` |
| `business_description` | String(200) | 否 | 业务描述 |
| `customer_id` | Integer (FK→customers) | 否 | 关联客户ID（可为空，解析后关联） |
| `sales_person_id` | Integer (FK→users) | 是 | 业务员ID（创建者） |
| `currency` | String(3) | 是 | 合同币种，默认 `CNY`，支持 `HKD`/`USD` |
| `total_amount` | DECIMAL(15,2) | 是 | 合同总金额 |
| `paid_amount` | DECIMAL(15,2) | 是 | 已付金额，默认 0 |
| `remaining_amount` | DECIMAL(15,2) | 否 | 剩余金额 = total_amount - paid_amount |
| `total_amount_in_cny` | DECIMAL(15,2) | 否 | 合同总额折算 CNY |
| `paid_amount_in_cny` | DECIMAL(15,2) | 否 | 已付折算 CNY |
| `remaining_amount_in_cny` | DECIMAL(15,2) | 否 | 剩余折算 CNY |
| `total_expense` | DECIMAL(15,2) | 否 | 总支出金额（默认 0） |
| `total_expense_in_cny` | DECIMAL(15,2) | 否 | 总支出折算 CNY（默认 0） |
| `original_file_path` | String(500) | 是 | 原始合同文件路径 |
| `file_hash` | String(64) | 否 | 文件 SHA256 哈希（用于重复检测） |
| `contract_data` | JSON | 是 | AI 解析的结构化数据（默认 `{}`） |
| `contract_text` | Text | 否 | 合同全文内容（AI 从图片/PDF 提取） |
| `confidence` | DECIMAL(5,4) | 否 | AI 解析置信度（0~1） |
| `needs_review` | Boolean | 否 | 是否需要人工审核（confidence < 0.85 时为 True） |
| `wechat_group` | String(200) | 否 | 业务微信群名称 |
| `status` | String(20) | 是 | 状态：`draft`/`active`/`completed`/`cancelled`/`disputed` |
| `signed_date` | Date | 否 | 签订日期 |
| `start_date` | Date | 否 | 生效日期 |
| `end_date` | Date | 否 | 到期日期 |
| `remarks` | Text | 否 | 备注 |
| `created_by` | Integer (FK→users) | 否 | 创建者 ID |
| `created_at` | DateTime | 是 | 创建时间（继承 BaseModel） |
| `updated_at` | DateTime | 是 | 更新时间（继承 BaseModel） |
| `is_deleted` | Boolean | 是 | 软删除标记（继承 BaseModel） |

**索引**：
- `idx_contracts_customer` (customer_id)
- `idx_contracts_sales` (sales_person_id)
- `idx_contracts_status` (status)
- `idx_contracts_signed_date` (signed_date)
- `idx_contracts_contract_number` (contract_number, unique)
- `idx_contracts_file_hash` (file_hash)
- `idx_contracts_data_gin` (contract_data, GIN 索引，支持 JSON 查询)

### 2.2 API 接口清单

**路由前缀**：`/api/v1/contracts` | **路由文件**：`backend/app/api/v1/contracts.py`

#### 2.2.1 创建合同（两种路径）

##### 路径 A：上传向导创建（推荐流程）

**这是一个多步骤向导，前端组件**：`frontend/src/components/ContractUploadWizard.tsx`

| 步骤 | API 端点 | 方法 | 说明 |
|------|---------|------|------|
| 1. 上传文件 | `POST /agent/upload` | POST | 上传合同文件到临时目录，返回 `file_id` |
| 2. AI 分析 | `POST /contracts/analyze-file` | POST | 同步分析已上传文件，返回结构化数据 + 重复检测 |
| 3. 关联客户 | `POST /contracts/resolve-customer` | POST | 从 AI 分析结果自动创建或关联客户 |
| 4. 创建合同 | `POST /contracts/create-from-analysis` | POST | 基于 AI 分析结果 + 用户确认数据创建合同 |

**`POST /contracts/analyze-file`** 详细说明：

- **请求体** (`AnalyzeFileRequest`)：
  ```json
  {
    "file_id": "string (必填，由 /agent/upload 返回)",
    "file_name": "string (可选，原始文件名)",
    "skip_duplicate_check": false
  }
  ```
- **响应**：`ResponseModel`，data 包含 AI 分析结果（合同各方信息、金额、付款条款、车辆信息等）
- **权限**：admin / income
- **实现位置**：`backend/app/services/contract_analyzer.py` → `ContractAnalyzer.analyze_file()`

**`POST /contracts/resolve-customer`** 详细说明：

- **请求体** (`ResolveCustomerRequest`)：
  ```json
  {
    "analysis_data": { "party_a": {...}, "party_b": {...} },
    "party": "party_b"
  }
  ```
- **处理逻辑**：
  1. 从 `analysis_data[party]` 提取 `name`/`phone`/`id_number`
  2. 调用 `CustomerService.create_or_get()` 执行去重 + 创建
  3. 返回 `{ success, customer: { id, name, phone, created } }`
- **如果未识别到姓名**：返回 `success: false`，前端展示手动输入表单
- **权限**：admin / income

**`POST /contracts/create-from-analysis`** 详细说明：

- **请求体** (`ContractCreateFromAnalysis`)：
  ```json
  {
    "file_id": "string",
    "customer_id": 123,
    "title": "合同标题",
    "business_type": "车辆买卖",
    "business_description": "奔驰GLS450",
    "currency": "CNY",
    "total_amount": 500000.00,
    "signed_date": "2026-06-01",
    "start_date": "2026-06-01",
    "end_date": "2026-12-31",
    "wechat_group": "xxx微信群",
    "payment_terms": [
      { "name": "定金", "amount": 100000, "due_date": "2026-06-01", "is_paid": true },
      { "name": "尾款", "amount": 400000, "due_date": "2026-07-01", "is_paid": false }
    ],
    "analysis_data": { ... },
    "full_text": "合同全文...",
    "confidence": 0.95,
    "remarks": "备注"
  }
  ```
- **处理逻辑**：
  1. 验证客户存在
  2. 生成唯一合同编号（`HT{timestamp}{4位随机}`）
  3. 将临时文件移动到永久合同目录
  4. 基于文件哈希进行重复检测（soft warning，不阻断）
  5. 调用 `ContractService.create_contract()` 创建合同
  6. 写入 `contract_data` JSON（含 source=wizard, file_id, payment_terms）
  7. 写入 `contract_text`（合同全文）
  8. 设置 `confidence` 和 `needs_review`（confidence < 0.85）
  9. 自动为 `is_paid=true` 的付款条款创建已支付的付款记录
- **权限**：admin / income

##### 路径 B：快速上传创建

| API 端点 | 方法 | 说明 |
|---------|------|------|
| `POST /contracts/upload-and-parse` | POST | 上传合同文件并立即创建草稿合同，后台 AI 解析 |

**`POST /contracts/upload-and-parse`** 详细说明：

- **请求格式**：`multipart/form-data`
  - `file`: 合同文件（必填，支持 JPEG/PNG/PDF）
  - `customer_id`: 客户 ID（可选）
- **处理逻辑**：
  1. 验证文件类型（魔数字节校验，支持 jpeg/png/pdf）
  2. 验证文件大小（不超过 `MAX_FILE_SIZE` 配置值）
  3. 保存文件到 `CONTRACT_UPLOAD_DIR`
  4. 生成合同编号
  5. 以 `status=draft` 创建合同（title=文件名，total_amount=0，currency=CNY）
  6. 提交 Celery 异步任务进行 AI 解析
- **响应**（HTTP 202）：
  ```json
  {
    "task_id": "celery-task-id",
    "status": "parsing",
    "contract_id": 456,
    "message": "合同上传成功，正在AI解析中..."
  }
  ```
- **权限**：admin / income

#### 2.2.2 查询合同

| API 端点 | 方法 | 说明 |
|---------|------|------|
| `GET /contracts` | GET | 合同列表（分页 + 多条件筛选） |
| `GET /contracts/{contract_id}` | GET | 合同详情 |
| `GET /contracts/parse-status/{contract_id}` | GET | 查询 AI 解析状态 |
| `GET /contracts/{contract_id}/file` | GET | 下载/预览合同原文件 |

**`GET /contracts`** 筛选参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `page` | int | 页码（默认 1） |
| `per_page` | int | 每页数量（默认 20，最大 500） |
| `status` | string | 合同状态筛选 |
| `customer_id` | int | 单个客户 ID |
| `customer_ids` | string | 多个客户 ID（逗号分隔，如 `1,3,5`） |
| `customer_name` | string | 客户名称模糊搜索（繁简兼容） |
| `keyword` | string | 全文搜索（合同编号/标题/JSON 数据） |
| `date_from` | date | 签订日期起始 |
| `date_to` | date | 签订日期结束 |

**权限控制**：
- admin/expense：查看全部合同
- income：仅查看 `sales_person_id == current_user.id` 的合同

**列表额外聚合**：每行自动附带 `paid_count`（已确认收入笔数）、`expense_count`（支出笔数）、`payment_total_count`（总付款笔数），通过一次 SQL GROUP BY 查询完成，避免 N+1 问题。

#### 2.2.3 更新与删除

| API 端点 | 方法 | 说明 | 权限 |
|---------|------|------|------|
| `PUT /contracts/{contract_id}` | PUT | 更新合同信息 | admin/income（仅自己合同） |
| `POST /contracts/{contract_id}/complete` | POST | 标记合同为已完成 | 仅 admin |
| `POST /contracts/{contract_id}/confirm-parsed-data` | POST | 确认/修正 AI 解析数据 | admin/income（仅自己合同） |
| `DELETE /contracts/{contract_id}` | DELETE | 删除合同 | 仅 admin |

**删除约束**（硬删除，非软删除）：
- 必须无关联付款记录（`Payment.is_deleted == False`），否则抛出 409 错误
- 同时清理物理合同文件
- 写入审计日志

### 2.3 合同编号生成规则

**代码位置**：`backend/app/services/contract_service.py` → `ContractService.generate_contract_number()`

```python
# 格式: HT + 时间戳(14位) + 4位随机hex(大写)
# 示例: HT20260606185530A3F2
return f"HT{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
```

### 2.4 合同状态流转

```
draft ──AI解析完成──► active ──管理员标记──► completed
  │                     │
  └── 删除               └── 删除（需无付款记录）
```

**状态含义**：
- `draft`：草稿（上传但尚未解析/确认）
- `active`：执行中（解析完成，正常履约）
- `completed`：已完成（管理员手动标记，或已收金额 ≥ 总金额时自动触发）
- `cancelled`：已取消
- `disputed`：有争议

### 2.5 业务类型枚举

**代码位置**：`backend/app/core/business_types.py`

| 标准值 | 说明 |
|--------|------|
| `车辆买卖` | 车辆买卖业务 |
| `两地牌过户` | 两地牌过户业务 |
| `年检保险` | 年检保险业务 |
| `其他` | 其他业务类型 |

**Legacy 兼容**：历史数据中的 `车辆业务` → 自动映射为 `车辆买卖`，`中港牌业务` → 自动映射为 `两地牌过户`。

---

## 3. 核心业务二：自动创建与关联客户

### 3.1 数据库模型

**表名**：`customers` | **模型文件**：`backend/app/models/customer.py`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | Integer (PK) | 是 | 自增主键 |
| `name` | String(200) | 是 | 客户名称 |
| `contact_person` | String(100) | 否 | 联系人 |
| `phone` | String(20) | 否 | 联系电话 |
| `email` | String(100) | 否 | 联系邮箱 |
| `id_card_number_encrypted` | Text | 否 | 身份证号（当前 base64 编码，计划升级 AES-GCM） |
| `business_license` | String(50) | 否 | 营业执照号 |
| `address` | Text | 否 | 地址 |
| `wechat_group_name` | String(200) | 否 | 微信群名称 |
| `remarks` | Text | 否 | 备注 |
| `created_by` | Integer (FK→users) | 否 | 创建者 ID |
| `created_at` / `updated_at` | DateTime | 是 | 时间戳（继承 BaseModel） |
| `is_deleted` | Boolean | 是 | 软删除标记 |

**约束**：`phone IS NOT NULL OR email IS NOT NULL`（电话和邮箱至少填写一项）

### 3.2 去重逻辑（核心）

**代码位置**：`backend/app/services/customer_service.py` → `CustomerService.create_or_get()`

```
去重规则：同名 + 同电话 → 返回已有客户
        同名 + 同邮箱 → 返回已有客户

流程：
1. 先按 (name, phone) 查询 → 命中则返回已有客户
2. 再按 (name, email) 查询 → 命中则返回已有客户
3. 都未命中 → 创建新客户

信息补充机制：
当匹配到已有客户时，将新传入的非空字段补写到已有客户的空字段中：
- id_card_number（仅当已有记录为空时补写）
- email（仅当已有记录为空时补写）
- address（仅当已有记录为空时补写）
- wechat_group_name（仅当已有记录为空时补写）
- business_license（仅当已有记录为空时补写）
- contact_person（仅当已有记录为空时补写）

返回值：(customer, was_created: bool)
```

### 3.3 客户创建触发场景

#### 场景 A：合同上传向导中自动触发

**前端流程**（`ContractUploadWizard.tsx`，Step 3）：

1. AI 分析完成后，自动调用 `POST /contracts/resolve-customer`
2. 传入 `analysis_data` 和 `party="party_b"`（party_b = 客户方）
3. 后端提取 `party_b.name`、`party_b.phone`、`party_b.id_number`
4. 调用 `CustomerService.create_or_get()` 执行去重逻辑
5. **如果未识别到姓名**：返回 `success: false`，前端展示手动输入表单（姓名 + 电话）
6. **如果识别成功**：返回客户信息，前端展示确认卡片 + "客户已存在"或"新客户已创建"标签

#### 场景 B：手动创建客户

**API**：`POST /api/v1/customers` | **前端页面**：`CustomerNew.tsx`

- **权限**：admin / income（expense 角色不可创建客户）
- **校验**：电话和邮箱至少填写一项
- **去重**：同名+同电话 或 同名+同邮箱 → 返回 409 Conflict

### 3.4 客户管理 API

| API 端点 | 方法 | 说明 | 权限 |
|---------|------|------|------|
| `GET /customers` | GET | 客户列表（分页 + 关键词搜索） | admin/income |
| `POST /customers` | POST | 创建客户 | admin/income |
| `GET /customers/{id}` | GET | 客户详情 | admin/income（仅自己创建） |
| `PUT /customers/{id}` | PUT | 更新客户 | admin/income（仅自己创建） |
| `DELETE /customers/{id}` | DELETE | 硬删除客户 | 仅 admin |

**列表搜索**：支持繁简中文兼容搜索（客户名称、微信群名称），通过 `backend/app/core/chinese.py` 中的 `search_variants()` 生成繁简搜索变体。

**删除约束**：客户有关联合同时拒绝删除（`active_contracts > 0` → ValueError）。

**权限隔离**：
- admin：查看全部客户
- income：仅查看 `created_by == current_user.id` 的客户
- expense：无权查看客户

---

## 4. 核心业务三：合同收入与支出录入

### 4.1 数据库模型

**表名**：`payments` | **模型文件**：`backend/app/models/payment.py`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | Integer (PK) | 是 | 自增主键 |
| `contract_id` | Integer (FK→contracts) | 是 | 关联合同 ID |
| `installment_number` | Integer | 是 | 期数编号（从 1 开始，收入/支出独立计数） |
| `installment_name` | String(100) | 否 | 期数名称（如"定金"、"保险费用"） |
| `type` | String(20) | 是 | 类型：`income`（收入）或 `expense`（支出） |
| `currency` | String(3) | 是 | 付款币种，默认 CNY |
| `amount` | DECIMAL(15,2) | 是 | 本期应付金额 |
| `paid_amount` | DECIMAL(15,2) | 否 | 实际已付金额（默认=amount） |
| `exchange_rate` | DECIMAL(10,6) | 否 | 使用的汇率 |
| `amount_in_cny` | DECIMAL(15,2) | 否 | 折算 CNY 金额 |
| `paid_amount_in_cny` | DECIMAL(15,2) | 否 | 已付折算 CNY |
| `due_date` | Date | 否 | 应付款日期 |
| `paid_date` | Date | 否 | 实际付款日期 |
| `receipt_image_path` | String(500) | 否 | 付款凭证图片路径 |
| `receipt_file_hash` | String(64) | 否 | 凭证文件哈希 |
| `receipt_ocr_text` | Text | 否 | OCR 识别文本 |
| `receipt_data` | JSON | 否 | 凭证 AI 分析结构化数据 |
| `payment_method` | String(20) | 否 | 付款方式：`bank_transfer`/`wechat`/`alipay`/`cash`/`check` |
| `payee_name` | String(200) | 否 | 收款方名称（**仅 expense 使用**） |
| `status` | String(20) | 是 | 状态：`pending`（待确认）/ `paid`（已确认） |
| `source` | String(20) | 否 | 来源：`manual`/`screenshot`/`upload` |
| `notes` | Text | 否 | 备注 |
| `description` | String(500) | 否 | 自动生成的可读描述 |
| `created_by` | Integer (FK→users) | 否 | 创建者 ID |

**唯一约束**：`(contract_id, installment_number, type)` — 同一合同的同一期数可以有一笔收入 + 一笔支出（各自独立计数）。

### 4.2 收入录入

#### 4.2.1 录入方式

##### 方式一：手动录入（带凭证上传）

**API**：`POST /payments/upload-receipt` | **代码位置**：`backend/app/api/v1/payments.py`

- **请求格式**：`multipart/form-data`
- **必填参数**：`contract_id`, `installment_number`, `paid_amount`, `paid_date`, `payment_method`
- **可选参数**：`currency`（默认 CNY）, `payment_type`（默认 income）, `file`（凭证图片）, `notes`, `payee_name`
- **处理逻辑**：
  1. 角色校验：income 角色只能创建 `type=income` 的记录
  2. 保存凭证文件（如有）
  3. 调用 `PaymentService.create_payment_with_exchange_rate()`
  4. 有凭证 → `status=paid`，自动累加合同已付金额
  5. 无凭证 → `status=pending`，不参与结算

##### 方式二：AI 凭证分析录入

**这是一个两步流程，前端组件**：`frontend/src/components/ReceiptPaymentModal.tsx`

| 步骤 | API 端点 | 方法 | 说明 |
|------|---------|------|------|
| 1. 上传+分析 | `POST /payments/analyze-receipt` | POST | 上传凭证 + 合同上下文 → AI 分析 + 匹配建议 |
| 2. 创建/匹配 | `POST /payments/create-from-receipt` | POST | 用户确认后创建新记录或匹配已有 pending 记录 |

**`POST /payments/analyze-receipt`** 详细说明：

- **请求格式**：`multipart/form-data`
- **参数**：`contract_id`, `payment_type`, `file`
- **处理逻辑**：
  1. 角色 + 合同权限校验
  2. 保存文件到临时目录
  3. 调用 `ReceiptAnalyzer.analyze_from_file()` 进行 AI 分析（同步）
  4. 仅 income 类型：查找合同下 `status=pending` 的已有记录，按金额相似度评分（最高 60 分）
     - 金额差 < 1：+50 分
     - 金额偏差 < 5%：+30 分
     - 币种相同：+10 分
  5. 返回分析结果 + 待匹配列表（Top 5）+ 下一个期数编号
- **响应**：
  ```json
  {
    "analysis": { "amount": 100000, "currency": "CNY", "transaction_date": "2026-06-01", ... },
    "temp_file_path": "/tmp/...",
    "pending_matches": [
      { "payment_id": 1, "installment_number": 1, "amount": 100000, "score": 60, "match_reason": "金额匹配度: 60" }
    ],
    "existing_payment_count": 2,
    "next_installment_number": 3
  }
  ```

**`POST /payments/create-from-receipt`** 详细说明：

- **两种分支**：
  - **分支 A**（`match_payment_id` 有值）：将凭证数据写入已有 pending 记录，状态从 pending → paid，触发合同金额结算
  - **分支 B**（`installment_number` 有值）：创建新付款记录，期数编号服务端实时重算（防并发冲突）
- **约束**：`match_payment_id` 和 `installment_number` 互斥且必须二选一
- **expense 类型**：`payee_name`（收款方）必填

#### 4.2.2 收入结算逻辑

**代码位置**：`backend/app/services/payment_service.py` → `_add_to_contract_paid()`

```
有凭证 (status=paid) 的收入记录创建时：

1. 同币种：contract.paid_amount += payment.paid_amount
2. 混币种：按 paid_date 汇率折算为合同币种后累加
3. 更新 contract.paid_amount_in_cny
4. 更新 contract.remaining_amount = total_amount - paid_amount
5. 更新 contract.remaining_amount_in_cny
6. 如果 paid_amount >= total_amount → 自动将合同状态设为 completed
```

### 4.3 支出录入

#### 4.3.1 录入方式

与收入录入完全相同的 API 和流程，区别在于：

| 差异点 | 收入 (income) | 支出 (expense) |
|--------|--------------|----------------|
| 角色权限 | admin / income | admin / expense |
| `payee_name` | 不需要 | **必填**（收款方名称） |
| 数据隔离 | 仅看 `sales_person_id` 为自己 + type=income | 仅看 `created_by` 为自己 + type=expense |
| 合同金额影响 | 累加 `paid_amount` | 累加 `total_expense` |
| 完成状态 | 已收 ≥ 总额 → completed | 不影响合同完成状态 |

#### 4.3.2 支出结算逻辑

**代码位置**：`backend/app/services/payment_service.py` → `_add_to_contract_expense()`

```
有凭证 (status=paid) 的支出记录创建时：

1. 同币种：contract.total_expense += payment.paid_amount
2. 混币种：按 paid_date 汇率折算为合同币种后累加
3. 更新 contract.total_expense_in_cny
4. 不影响合同完成状态（支出不改变 completed 判断）
```

### 4.4 汇率结算机制

**代码位置**：`backend/app/services/payment_service.py` + `backend/app/services/exchange_rate_service.py`

```
结算触发时机：有凭证的付款记录创建时

纯 CNY 场景（contract.currency=CNY AND payment.currency=CNY）：
  - exchange_rate = None
  - amount_in_cny = None
  - 不进行任何汇率换算

非纯 CNY 场景（任一非 CNY）：
  - 调用 ExchangeRateService.convert_to_cny(amount, currency, paid_date)
  - 按 paid_date 日期查询最新汇率
  - 计算 amount_in_cny = amount × exchange_rate
  - 存储到 payment.exchange_rate 和 payment.amount_in_cny

混币种累加（payment.currency ≠ contract.currency）：
  - 调用 ExchangeRateService.convert_currency(amount, from_cur, to_cur, date)
  - 折算为合同币种后累加到 contract.paid_amount / contract.total_expense
```

### 4.5 删除付款记录的反写逻辑

**代码位置**：`backend/app/services/payment_service.py` → `delete_payment()`

```
硬删除（仅 admin）：

1. 清理凭证物理文件
2. 如果 status=paid（已参与结算）：
   - 收入：扣减 contract.paid_amount / paid_amount_in_cny
         重算 remaining_amount / remaining_amount_in_cny
         如果合同原为 completed，检查是否仍需保持（兜底回退到 active）
   - 支出：扣减 contract.total_expense / total_expense_in_cny
3. 写入审计日志
```

### 4.6 付款记录查询

| API 端点 | 方法 | 说明 | 权限 |
|---------|------|------|------|
| `GET /payments` | GET | 付款记录列表（分页 + 多条件筛选） | 全部（角色自动过滤） |
| `GET /payments/contract/{contract_id}` | GET | 合同付款详情（含收入/支出分组 + 利润） | 全部（角色过滤类型） |

**`GET /payments` 筛选参数**：

| 参数 | 说明 |
|------|------|
| `page`, `per_page` | 分页 |
| `contract_id` | 合同 ID |
| `keyword` | 搜索（合同编号/客户名称） |
| `status` | 状态筛选 |
| `type` | 类型筛选 (income/expense) |
| `date_from`, `date_to` | 付款日期范围 |

**角色数据隔离**（后端 SQL 层实现）：
- **income 角色**：自动附加 `type='income' AND sales_person_id=current_user.id`
- **expense 角色**：自动附加 `type='expense' AND created_by=current_user.id`
- **admin 角色**：全量数据

**`GET /payments/contract/{contract_id}` 响应结构**：

```json
{
  "contract_id": 1,
  "contract_number": "HT20260606185530A3F2",
  "income": {
    "payments": [...],
    "total_amount": 500000,
    "paid_amount": 100000,
    "remaining_amount": 400000,
    "total_paid_in_cny": 100000
  },
  "expense": {
    "payments": [...],
    "total_expense": 5000,
    "total_expense_in_cny": 5000
  },
  "profit_in_cny": 95000
}
```

**利润计算公式**：`profit_in_cny = total_paid_in_cny - total_expense_in_cny`

- CNY 合同：直接用 `paid_amount` - `total_expense`（原值即 CNY）
- 非 CNY 合同：用 `paid_amount_in_cny` - `total_expense_in_cny`

### 4.7 自动生成的可读描述

**代码位置**：`backend/app/services/payment_service.py` → `_generate_description()`

```
优先级：
1. installment_name（如"定金"、"第一期车款"）→ 直接使用
2. contract.business_description（如"奔驰GLS450"）→ 直接使用
3. 兜底：如 type=income → "第N期收款"；type=expense → "第N期支出→收款方名称"
```

---

## 5. 角色权限模型

**代码位置**：`backend/app/core/permissions.py`

| 角色 | 常量 | 可创建合同 | 可查看客户 | 可录入收入 | 可录入支出 | 可管理用户 |
|------|------|-----------|-----------|-----------|-----------|-----------|
| 管理员 | `admin` | ✅ | ✅ (全部) | ✅ (全部) | ✅ (全部) | ✅ |
| 收入岗 | `income` | ✅ | ✅ (仅自己创建) | ✅ (仅自己合同) | ❌ | ❌ |
| 支出岗 | `expense` | ❌ | ❌ | ❌ | ✅ (仅自己创建) | ❌ |

**数据隔离总结**：

| 实体 | admin | income | expense |
|------|-------|--------|---------|
| 合同列表 | 全部 | `sales_person_id = self` | 全部（只读） |
| 合同详情/修改 | 全部 | 仅自己合同 | 只读 |
| 客户列表 | 全部 | `created_by = self` | 403 |
| 付款收入 | 全部 | type=income + 自己合同 | 403 |
| 付款支出 | 全部 | 403 | type=expense + `created_by = self` |
| 删除操作 | 全部 | ❌ | ❌ |

---

## 6. 核心数据模型关系图

```
┌──────────────┐         ┌──────────────────────┐
│    users     │         │     customers        │
│              │         │                      │
│ id (PK)      │◄────────│ created_by (FK)      │
│ username     │         │ name                 │
│ role         │         │ phone                │
│   admin      │         │ email                │
│   income     │         │ id_card_number_enc   │
│   expense    │         │ wechat_group_name    │
└──────┬───────┘         └──────────┬───────────┘
       │                            │
       │ sales_person_id (FK)       │ customer_id (FK)
       │                            │
       ▼                            ▼
┌──────────────────────────────────────────────────────┐
│                    contracts                         │
│                                                      │
│ id (PK)                                              │
│ contract_number (UNIQUE)  ←─ HT{timestamp}{4hex}     │
│ business_type             ←─ 车辆买卖/两地牌过户/...   │
│ currency                  ←─ CNY/HKD/USD             │
│ total_amount              ←─ 合同总额                 │
│ paid_amount               ←─ 已收（由 income payments│
│ remaining_amount          ←─ 剩余 = total - paid      │
│ total_expense             ←─ 总支出（由 expense）      │
│ *_in_cny                  ←─ CNY 折算字段             │
│ status                    ←─ draft/active/completed   │
│ contract_data (JSON)      ←─ AI 解析结果              │
│ contract_text             ←─ 合同全文                 │
│ confidence                ←─ AI 置信度                │
│ original_file_path        ←─ 合同文件路径              │
└─────────────┬────────────────────────────────────────┘
              │
              │ contract_id (FK)
              │
              ▼
┌──────────────────────────────────────────────────────┐
│                    payments                          │
│                                                      │
│ id (PK)                                              │
│ contract_id (FK)                                     │
│ installment_number    ←─ 期数（收入/支出独立计数）     │
│ installment_name      ←─ 期数名称（如"定金"）          │
│ type                  ←─ income / expense            │
│ currency              ←─ CNY/HKD/USD                 │
│ amount / paid_amount                                 │
│ exchange_rate / *_in_cny  ←─ 汇率结算                 │
│ paid_date             ←─ 实际付款日期（汇率查询基准）   │
│ payment_method        ←─ bank_transfer/wechat/...    │
│ payee_name            ←─ 收款方（仅 expense）          │
│ status                ←─ pending(待确认) / paid(已确认)│
│ receipt_image_path    ←─ 凭证图片                     │
│ receipt_data (JSON)   ←─ AI 分析结果                  │
│ description           ←─ 自动生成描述                 │
│                                                      │
│ UNIQUE(contract_id, installment_number, type)        │
└──────────────────────────────────────────────────────┘
```

---

## 7. 核心业务数据流

### 7.1 合同创建完整流程（上传向导路径）

```
┌────────────────────────────────────────────────────────────┐
│ 前端 ContractUploadWizard (4 步向导)                        │
│                                                            │
│ Step 1: 上传文件                                            │
│   POST /agent/upload                                       │
│   → 返回 file_id                                            │
│                                                            │
│ Step 2: AI 分析                                            │
│   POST /contracts/analyze-file { file_id }                 │
│   → ContractAnalyzer.analyze_file()                        │
│   → 调用 VL 模型分析合同图片/PDF                            │
│   → 返回: { party_a, party_b, total_amount, currency,     │
│              payment_terms, vehicle_info, confidence, ... } │
│   → 同时进行重复检测（按 file_hash）                         │
│                                                            │
│ Step 3: 自动关联客户                                        │
│   POST /contracts/resolve-customer { analysis_data, party }│
│   → CustomerService.create_or_get(name, phone, id_number)  │
│   → 去重: 同名+同电话 或 同名+同邮箱                         │
│   → 返回: { id, name, phone, created: bool }               │
│   → 如果失败: 前端展示手动输入表单                           │
│                                                            │
│ Step 4: 确认并创建合同                                      │
│   POST /contracts/create-from-analysis { ... }             │
│   → 验证客户存在                                            │
│   → 生成合同编号 HT{timestamp}{hex}                         │
│   → 移动文件到永久目录                                       │
│   → ContractService.create_contract()                      │
│   → 非 CNY 合同: 计算 total_amount_in_cny                   │
│   → 写入 contract_data JSON                                │
│   → 写入 contract_text                                     │
│   → 设置 confidence / needs_review                         │
│   → 自动创建 is_paid=true 的付款记录                        │
│   → 返回合同信息 + auto_payments                           │
└────────────────────────────────────────────────────────────┘
```

### 7.2 收入/支出录入流程

```
┌────────────────────────────────────────────────────────────┐
│ 方式一：手动录入 (ReceiptPaymentModal / 直接表单)           │
│                                                            │
│ POST /payments/upload-receipt                              │
│   → 校验角色权限（income 只能 income，expense 只能 expense）│
│   → 保存凭证文件（如有）                                     │
│   → PaymentService.create_payment_with_exchange_rate()     │
│     ├─ 查询汇率（非纯 CNY 场景）                             │
│     ├─ 有凭证 → status=paid + 累加合同金额                   │
│     │   ├─ income: contract.paid_amount += amount          │
│     │   │   paid_amount >= total_amount → status=completed │
│     │   └─ expense: contract.total_expense += amount       │
│     └─ 无凭证 → status=pending（不参与结算）                 │
│                                                            │
│ 方式二：AI 凭证分析录入 (ReceiptPaymentModal)                │
│                                                            │
│ Step 1: POST /payments/analyze-receipt                     │
│   → ReceiptAnalyzer.analyze_from_file() (VL 模型)          │
│   → 返回 AI 分析结果 + pending 匹配建议（金额相似度评分）    │
│                                                            │
│ Step 2: POST /payments/create-from-receipt                 │
│   → 分支 A (match_payment_id): 更新已有 pending → paid     │
│   → 分支 B (installment_number): 创建新记录              │
│   → 服务端实时重算 installment_number（防并发）             │
│   → 迁移临时文件到永久目录                                   │
└────────────────────────────────────────────────────────────┘
```

### 7.3 合同详情页数据聚合

```
GET /contracts/{id} + GET /payments/contract/{id}

前端 ContractDetail.tsx 渲染:

┌─ 顶部信息条 ──────────────────────────────────┐
│ [状态标签] [业务类型] 👤客户名称 — 合同标题     │
│ HT2026...  · 签订日期  · CNY                    │
├─ 财务概览面板 ──────────────────────────────────┤
│ 合同总额  ¥500,000   收款进度 [====] 20%        │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │
│ │已收   │ │剩余   │ │总支出 │ │净利润  │          │
│ │¥100K │ │¥400K │ │¥5K   │ │¥95K  │          │
│ └──────┘ └──────┘ └──────┘ └──────┘          │
├─ 业务信息 + 车辆信息 ────────────────────────────┤
│ 业务描述 | 证件号码 | 客户电话 | 微信群 | 备注   │
│ 车牌号 | 车型 | 通行口岸                        │
├─ 付款条款（步骤图）─────────────────────────────│
│ ① 定金 ─────── ¥100,000                        │
│ ② 尾款 ─────── ¥400,000   约定付款: 2026-07-01 │
├─ 合同文件 ──────────────────────────────────────│
│ 📄 查看原文件                                    │
├─ 收付记录 ──────────────────────────────────────│
│ [收入记录 (2)] [支出记录 (1)]                    │
│ ┌─ 第1期 ✅ ─── ¥100,000 ─── 2026-06-01 ─── 凭证│
│ └─ 第2期 ⏳ ─── ¥400,000 ─── 待收               │
└────────────────────────────────────────────────┘
```

---

## 附录 A：关键代码文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/api/v1/contracts.py` | 合同 API 路由（588 行） |
| `backend/app/api/v1/customers.py` | 客户 API 路由（244 行） |
| `backend/app/api/v1/payments.py` | 付款 API 路由（492 行） |
| `backend/app/services/contract_service.py` | 合同服务层（388 行） |
| `backend/app/services/customer_service.py` | 客户服务层（152 行） |
| `backend/app/services/payment_service.py` | 付款服务层（373 行） |
| `backend/app/models/contract.py` | 合同 ORM 模型 |
| `backend/app/models/customer.py` | 客户 ORM 模型 |
| `backend/app/models/payment.py` | 付款 ORM 模型 |
| `backend/app/schemas/contract.py` | 合同 Pydantic Schema |
| `backend/app/schemas/customer.py` | 客户 Pydantic Schema |
| `backend/app/schemas/payment.py` | 付款 Pydantic Schema |
| `backend/app/core/business_types.py` | 业务类型枚举 |
| `backend/app/core/permissions.py` | 角色权限模块 |
| `frontend/src/pages/ContractDetail.tsx` | 合同详情页 |
| `frontend/src/pages/ContractList.tsx` | 合同列表页 |
| `frontend/src/pages/PaymentList.tsx` | 收付管理页 |
| `frontend/src/components/ContractUploadWizard.tsx` | 合同上传向导 |
| `frontend/src/components/ReceiptPaymentModal.tsx` | 凭证录入弹窗 |
| `frontend/src/services/contract.ts` | 合同前端 API |
| `frontend/src/services/payment.ts` | 付款前端 API |

---

## 附录 B：审查声明

本文档已完成**严格的代码对照审查**，审查范围包括：

- ✅ 所有 API 端点名称、方法、参数与实际代码一致
- ✅ 所有数据库字段名、类型、约束与实际模型一致
- ✅ 所有业务逻辑描述与实际服务层代码一致
- ✅ 所有角色权限规则与 `permissions.py` 一致
- ✅ 所有前端页面路由、组件名与实际代码一致
- ✅ 汇率结算、金额累加、完成状态判定等计算逻辑与 `payment_service.py` 一致
- ✅ 去重逻辑与 `customer_service.py` 一致
- ✅ 合同编号生成规则与 `contract_service.py` 一致

**未覆盖的内容**（按要求排除）：
- 用户认证/授权体系详情
- AI 智能问答（Agent）模块
- 财务统计模块
- 汇率管理模块
- 文件管理模块
- LangGraph 编排层
- 部署/运维相关
