# 企业级合同管理与智能客服Agent系统 - 技术规格说明书

## 📋 文档版本控制

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | 2026-05-25 | Qoder | 初始版本，完整技术规格定义 |
| v1.1 | 2026-05-25 | Qoder | **新增多币种与汇率管理模块**：<br/>• 合同/付款支持CNY/HKD多币种<br/>• 新增exchange_rates汇率表<br/>• 付款时按登记日期自动查询汇率并折算CNY<br/>• 新增汇率管理服务API |

---

## 1️ 项目概述

### 1.1 业务背景

华星资源开发有限公司主营业务包括：
- 两地车牌指标过户服务
- 车辆买卖服务
- 其他相关商务服务

**当前痛点：**
1. 合同以纸质/图片形式存储，无法快速检索和统计
2. 付款记录分散在微信群、Excel、纸质单据中，尾款计算容易出错
3. 客户服务依赖微信群人工沟通，信息孤岛严重
4. 缺乏统一的业务数据管理和查询能力
5. 历史合同查找困难，特别是需要从图片中识别关键信息

### 1.2 项目目标

构建一个**企业级私有知识库 + AI Agent系统**，实现：

#### 核心功能
1. **合同智能管理**
   - 上传合同图片/PDF → AI自动解析提取关键信息
   - 结构化存储到数据库（客户信息、服务内容、金额、付款计划等）
   - 支持全文搜索、语义搜索、条件筛选
   - **多币种支持**：合同金额可以是CNY或HKD

2. **付款自动跟踪**
   - 支持自定义多期付款（不限期数）
   - 上传付款凭证图片（转账截图、银行回单等）→ AI自动识别金额/日期
   - **多币种付款**：每次付款可以是CNY或HKD，按付款登记时实时汇率折算
   - **自动汇率结算**：根据付款日期自动获取当日汇率，统一折算为基准币种（CNY）
   - 自动计算已付金额、剩余尾款、逾期情况
   - 生成费用单/对账单

3. **智能问答Agent**
   - 自然语言查询："张三还欠多少钱？"、"上个月签了多少合同？"
   - 基于真实数据库数据回答，避免AI幻觉
   - 对话历史保存，支持上下文追问

4. **微信截图半自动处理**
   - 业务员从微信群截图（包含付款通知、客户消息等）
   - 上传到系统后，AI自动识别：
     - 群名称（用于关联客户/业务）
     - 关键信息（付款金额、时间、客户姓名等）
   - 人工确认关联到对应合同或客户

5. **文件存储与检索**
   - 合同原件存档（图片/PDF）
   - 付款凭证存档（图片）
   - 微信截图存档
   - OCR全文索引，支持内容搜索

#### 非功能性要求
- **安全性**：JWT认证 + RBAC权限控制 + 敏感数据加密
- **性能**：合同列表加载 < 500ms，AI解析 < 30秒
- **可扩展性**：模块化设计，便于后续增加新业务类型
- **可维护性**：完整文档、测试覆盖、代码规范

---

## 2️⃣ 技术架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        客户端层                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Web浏览器 (React SPA)                    │   │
│  │  • 合同管理页面                                        │   │
│  │  • 付款跟踪看板                                        │   │
│  │  • 智能问答聊天界面                                     │   │
│  │  • 文件上传组件                                        │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS / REST API + JSON
┌──────────────────────────▼──────────────────────────────────┐
│                     API网关层 (可选)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Nginx / Traefik                             │   │
│  │  • 反向代理                                            │   │
│  │  • SSL终止                                             │   │
│  │  • 限流防刷                                            │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   应用层 (FastAPI Backend)                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Auth模块    │  │ Contract模块 │  │ Payment模块      │   │
│  │ • JWT认证   │  │ • CRUD       │  │ • 分期付款       │   │
│  │ • RBAC权限  │  │ • AI解析     │  │ • 凭证识别       │   │
│  │ • 用户管理  │  │ • 状态流转   │  │ • 尾款计算       │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ File模块    │  │ Search模块   │  │ Agent模块        │   │
│  │ • 上传下载  │  │ • 全文搜索   │  │ • 意图识别       │   │
│  │ • 本地存储  │  │ • 向量检索   │  │ • SQL构建        │   │
│  │ • OCR索引   │  │ • 混合搜索   │  │ • LLM回答生成    │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         异步任务层 (Celery + Redis)                    │   │
│  │  • 合同解析任务                                        │   │
│  │  • 凭证OCR任务                                         │   │
│  │  • 批量导入任务                                        │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    基础设施层                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ PostgreSQL   │  │ 本地文件系统 │  │ Redis            │   │
│  │ • 关系数据   │  │ • 合同文件   │  │ • 会话缓存       │   │
│  │ • JSONB      │  │ • 付款凭证   │  │ • 任务队列       │   │
│  │ • 全文搜索   │  │ • 微信截图   │  │ • 限流计数       │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         外部AI服务 (SiliconFlow API)                   │   │
│  │  • Qwen3-VL-32B-Instruct (视觉解析)                   │   │
│  │  • Qwen3-VL-8B-Instruct (文本理解)                    │   │
│  └──────────────────────────────────────────────────────┘   │
─────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈选型

| 层级 | 技术选型 | 版本 | 选型理由 |
|------|---------|------|----------|
| **后端框架** | Python FastAPI | 0.109+ | 异步高性能、自动OpenAPI文档、Pydantic数据验证 |
| **ORM框架** | SQLAlchemy | 2.0+ | 成熟的Python ORM、支持async、Alembic迁移工具 |
| **数据库** | PostgreSQL | 15+ | JSONB灵活存储、GIN索引、全文搜索、事务ACID |
| **缓存/队列** | Redis | 7+ | 会话缓存、Celery任务队列、限流计数器 |
| **异步任务** | Celery | 5.3+ | 分布式任务队列、支持定时任务、结果回溯 |
| **AI模型-视觉** | Qwen3-VL-32B-Instruct | - | 通过SiliconFlow调用，32B参数OCR能力强 |
| **AI模型-文本** | Qwen3-VL-8B-Instruct | - | 通过SiliconFlow调用，8B参数成本低速度快 |
| **前端框架** | React | 18.2+ | 生态成熟、TypeScript支持好、Ant Design组件库 |
| **前端语言** | TypeScript | 5.3+ | 类型安全、与后端Pydantic模型对应 |
| **UI组件库** | Ant Design | 5.12+ | 企业级UI设计语言、组件丰富 |
| **状态管理** | Zustand | 4.4+ | 轻量简洁、比Redux易上手 |
| **HTTP客户端** | Axios | 1.6+ | 成熟稳定、拦截器机制完善 |
| **文件存储** | 本地文件系统 | - | 一期简单直接，后续可无缝切换到MinIO/OSS |
| **部署方式** | 原生服务 | - | 直接部署，systemd管理进程 |
| **Web服务器** | Nginx | 1.24+ | 反向代理、静态文件服务、SSL终止 |
| **日志系统** | Python logging + ELK | - | 结构化日志、便于排查问题 |
| **监控告警** | Prometheus + Grafana | - | 二期考虑，一期暂不实施 |

### 2.3 目录结构

```
contract-management-system/
├── README.md                          # 项目说明文档
├── SPEC.md                            # 本技术规格说明书
├── pyproject.toml                     # Poetry依赖管理
├── requirements.txt                   # pip依赖（备选）
├── .env.example                       # 环境变量模板
├── .gitignore
│
├── backend/                           # FastAPI后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI应用入口
│   │   ├── config.py                  # 配置管理（读取.env）
│   │   │
│   │   ├── api/                       # API路由层
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py            # 认证接口
│   │   │   │   ├── customers.py       # 客户接口
│   │   │   │   ├── contracts.py       # 合同接口
│   │   │   │   ├── payments.py        # 付款接口
│   │   │   │   ├── agent.py           # 智能问答接口
│   │   │   │   └── files.py           # 文件接口
│   │   │   │
│   │   │   └── dependencies.py        # 依赖注入（获取当前用户、DB会话等）
│   │   │
│   │   ├── core/                      # 核心模块
│   │   │   ├── __init__.py
│   │   │   ├── security.py            # JWT、密码加密
│   │   │   ├── exceptions.py          # 自定义异常类
│   │   │   ├── middleware.py          # 中间件（CORS、日志、错误处理）
│   │   │   └── config.py              # 环境变量读取
│   │   │
│   │   ├── models/                    # SQLAlchemy ORM模型
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # 基类（id, created_at, updated_at）
│   │   │   ├── user.py                # 用户表
│   │   │   ├── customer.py            # 客户表
│   │   │   ├── contract.py            # 合同表
│   │   │   ├── payment.py             # 付款表
│   │   │   └── file.py                # 文件元数据表
│   │   │
│   │   ├── schemas/                   # Pydantic数据模型
│   │   │   ├── __init__.py
│   │   │   ├── user.py                # 用户请求/响应模型
│   │   │   ├── customer.py            # 客户请求/响应模型
│   │   │   ├── contract.py            # 合同请求/响应模型
│   │   │   ├── payment.py             # 付款请求/响应模型
│   │   │   ├── agent.py               # 问答请求/响应模型
│   │   │   └── response.py            # 统一响应格式
│   │   │
│   │   ├── services/                  # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py        # 认证服务
│   │   │   ├── customer_service.py    # 客户服务
│   │   │   ├── contract_service.py    # 合同服务
│   │   │   ├── payment_service.py     # 付款服务
│   │   │   ├── file_service.py        # 文件服务
│   │   │   └── agent_service.py       # 智能问答服务
│   │   │
│   │   ├── ai/                        # AI集成模块
│   │   │   ├── __init__.py
│   │   │   ├── llm_client.py          # SiliconFlow API客户端
│   │   │   ├── contract_parser.py     # 合同解析器
│   │   │   ├── receipt_ocr.py         # 付款凭证OCR
│   │   │   ├── wechat_screenshot.py   # 微信截图识别
│   │   │   └── prompts.py             # Prompt模板管理
│   │   │
│   │   ├── tasks/                     # 异步任务
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py          # Celery配置
│   │   │   ├── contract_tasks.py      # 合同解析任务
│   │   │   └── ocr_tasks.py           # OCR任务
│   │   │
│   │   └── utils/                     # 工具函数
│   │       ├── __init__.py
│   │       ├── file_utils.py          # 文件操作（保存、哈希计算）
│   │       ├── validators.py          # 数据验证
│   │       └── helpers.py             # 辅助函数
│   │
│   ├── tests/                         # 测试
│   │   ├── __init__.py
│   │   ├── conftest.py                # pytest配置
│   │   ├── test_auth.py               # 认证测试
│   │   ├── test_customers.py          # 客户测试
│   │   ├── test_contracts.py          # 合同测试
│   │   ├── test_payments.py           # 付款测试
│   │   └── test_ai_parsing.py         # AI解析测试
│   │
│   └── migrations/                    # Alembic数据库迁移
│       ├── versions/                  # 迁移脚本
│       ├── env.py
│       └── script.py.mako
│
├── frontend/                          # React前端
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts                 # Vite构建配置
│   ├── index.html
│   └── src/
│       ├── main.tsx                   # 入口文件
│       ├── App.tsx                    # 根组件
│       ├── components/                # 公共组件
│       │   ├── Layout.tsx             # 布局组件
│       │   ├── UploadFile.tsx         # 文件上传组件
│       │   └── ...
│       ├── pages/                     # 页面组件
│       │   ├── Login.tsx              # 登录页
│       │   ├── CustomerList.tsx       # 客户列表
│       │   ├── CustomerDetail.tsx     # 客户详情
│       │   ├── ContractList.tsx       # 合同列表
│       │   ├── ContractDetail.tsx     # 合同详情
│       │   ├── ContractUpload.tsx     # 合同上传
│       │   ├── PaymentList.tsx        # 付款列表
│       │   └── AgentChat.tsx          # 智能问答
│       ├── services/                  # API调用
│       │   ├── api.ts                 # Axios实例配置
│       │   ├── auth.ts                # 认证API
│       │   ├── customer.ts            # 客户API
│       │   ├── contract.ts            # 合同API
│       │   ├── payment.ts             # 付款API
│       │   └── agent.ts               # 问答API
│       ├── store/                     # 状态管理
│       │   ├── useAuthStore.ts        # 认证状态
│       │   └── ...
│       ├── types/                     # TypeScript类型定义
│       │   └── index.ts
│       └── utils/                     # 工具函数
│           └── helpers.ts
│
├── data/                              # 数据存储目录（运行时生成）
│   ├── contracts/                     # 合同原件
│   │   ── {year}/{month}/
│   ├── receipts/                      # 付款凭证
│   │   └── {year}/{month}/
│   ├── screenshots/                   # 微信截图
│   │   └── {year}/{month}/
│   └── backups/                       # 数据库备份
│
└── docs/                              # 文档
    ├── architecture.md                # 架构设计文档
    ├── api-spec.md                    # API接口文档
    ├── deployment.md                  # 部署指南
    ── user-manual.md                 # 用户手册
```

---

## 3️ 数据库设计

### 3.1 ER图

```
┌──────────────       ┌──────────────┐       ┌──────────────────┐
│    users     │       │   customers  │       │    contracts     │
──────────────┤       ├──────────────┤       ├──────────────────┤
│ id (PK)      │       │ id (PK)      │       │ id (PK)          │
│ username     │1────*│ name         │1────*│ contract_number  │
│ password_hash│       │ contact_name │       │ customer_id (FK) │
│ email        │       │ phone        │       │ sales_person_id  │
│ full_name    │       │ email        │       │ total_amount     │
│ role         │       │ address      │       │ paid_amount      │
│ is_active    │       │ remarks      │       │ remaining_amount │
│ created_at   │       │ created_by   │       │ status           │
│ updated_at   │       │ created_at   │       │ contract_data    │
└──────────────┘       └──────────────┘       │ file_path        │
                                              │ signed_date      │
                                              │ created_at       │
                                              └────────┬─────────┘
                                                       │1
                                                       │
                                                       │*
                                          ┌────────────▼─────────┐
                                          │   payments           │
                                          ├──────────────────────┤
                                          │ id (PK)              │
                                          │ contract_id (FK)     │
                                          │ installment_number   │
                                          │ installment_name     │
                                          │ amount               │
                                          │ paid_amount          │
                                          │ due_date             │
                                          │ paid_date            │
                                          │ receipt_image_path   │
                                          │ status               │
                                          │ created_at           │
                                          ──────────────────────┘
```

### 3.2 详细Schema

#### 3.2.1 用户表 (users)

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,           -- 用户名（登录用）
    password_hash VARCHAR(255) NOT NULL,            -- 密码哈希（bcrypt）
    email VARCHAR(100) UNIQUE,                      -- 邮箱
    full_name VARCHAR(100),                         -- 真实姓名
    role VARCHAR(20) NOT NULL DEFAULT 'sales',      -- 角色: admin/sales/viewer/finance
    department VARCHAR(50),                         -- 部门
    is_active BOOLEAN DEFAULT TRUE,                 -- 是否激活
    last_login_at TIMESTAMP WITH TIME ZONE,         -- 最后登录时间
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- 初始数据
INSERT INTO users (username, password_hash, email, full_name, role) VALUES
('admin', '$2b$12$...', 'admin@huaxing.com', '系统管理员', 'admin');
```

**字段说明：**
- `role` 枚举值：
  - `admin`: 管理员（全部权限）
  - `sales`: 业务员（只能看自己负责的客户）
  - `viewer`: 查看者（只读权限）
  - `finance`: 财务（可查看/审核付款）

#### 3.2.2 客户表 (customers)

```sql
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,                     -- 客户名称（公司名或个人姓名）
    contact_person VARCHAR(100),                    -- 联系人
    phone VARCHAR(20),                              -- 联系电话
    email VARCHAR(100),                             -- 联系邮箱
    id_card_number_encrypted TEXT,                  -- 身份证号（加密存储）
    business_license VARCHAR(50),                   -- 营业执照号
    address TEXT,                                   -- 地址
    wechat_group_name VARCHAR(200),                 -- 微信群名称（用于关联截图）
    remarks TEXT,                                   -- 备注
    
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- 创建者
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_phone_or_email CHECK (phone IS NOT NULL OR email IS NOT NULL)
);

-- 索引
CREATE INDEX idx_customers_name ON customers(name);
CREATE INDEX idx_customers_phone ON customers(phone);
CREATE INDEX idx_customers_created_by ON customers(created_by);
CREATE INDEX idx_customers_wechat_group ON customers(wechat_group_name);
```

**字段说明：**
- `wechat_group_name`: 存储该客户对应的微信群名称，用于AI识别截图时自动关联
- `id_card_number_encrypted`: 敏感信息加密存储（使用Fernet对称加密）

#### 3.2.3 合同表 (contracts) ⭐ 核心表

```sql
CREATE TABLE contracts (
    id SERIAL PRIMARY KEY,
    
    -- 合同基本信息
    contract_number VARCHAR(50) UNIQUE NOT NULL,    -- 合同编号（如 HT20260525001）
    title VARCHAR(500),                             -- 合同标题
    
    -- 关联关系
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    sales_person_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    
    -- 金额相关 ⭐ 增加币种支持
    currency VARCHAR(3) NOT NULL DEFAULT 'CNY',     -- 合同币种: CNY/HKD/USD
    total_amount DECIMAL(15, 2) NOT NULL DEFAULT 0, -- 合同总金额（原始币种）
    paid_amount DECIMAL(15, 2) NOT NULL DEFAULT 0,  -- 已付金额（原始币种，冗余字段）
    remaining_amount DECIMAL(15, 2) GENERATED ALWAYS AS (total_amount - paid_amount) STORED,
    
    -- 折算CNY金额（用于统计汇总）⭐ 新增
    total_amount_in_cny DECIMAL(15, 2),             -- 合同总额折算CNY（按签订日汇率）
    paid_amount_in_cny DECIMAL(15, 2) DEFAULT 0,    -- 已付金额折算CNY
    remaining_amount_in_cny DECIMAL(15, 2) GENERATED ALWAYS AS (COALESCE(total_amount_in_cny, 0) - paid_amount_in_cny) STORED,
    
    -- 合同文件
    original_file_path VARCHAR(500) NOT NULL,       -- 原始合同文件相对路径
    file_hash VARCHAR(64),                          -- 文件SHA256哈希（防重复）
    
    -- AI解析的结构化数据（JSONB）⭐ 关键字段
    contract_data JSONB NOT NULL DEFAULT '{}',
    /*
    contract_data 结构示例（基于真实合同样本）：
    {
        "party_a": {
            "name": "华星智源开发有限公司",
            "contact": "98702065",
            "address": null
        },
        "party_b": {
            "name": "卢灿梅",
            "id_type": "身份证",
            "id_number": "M60390A(7)",
            "address": "54902790"
        },
        "service_content": {
            "description": "两地车牌指标过户服务",
            "license_plate": "粤ZS629港",
            "port": "莲塘口岸",
            "old_license_plate": null,
            "new_license_plate": "蓝牌口岸"
        },
        "payment_terms": [
            {
                "type": "deposit",
                "name": "定金",
                "amount": 20000,
                "condition": "合同签订日",
                "due_date": null
            },
            {
                "type": "final",
                "name": "尾款",
                "amount": 215000,
                "condition": "完成过户手续后",
                "due_date": null
            }
        ],
        "total_amount": 235000,
        "signed_date": "2026-05-25",
        "contract_type": "vehicle_license_transfer",
        "special_clauses": [
            "甲方不承担乙方受让前目标公司的任何债务",
            "若因乙方原因导致过户失败，甲方退还已收取的服务费"
        ]
    }
    */
    
    -- 合同状态
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- 枚举值: draft(草稿), active(执行中), completed(已完成), cancelled(已取消), disputed(争议)
    
    -- 时间字段
    signed_date DATE,                               -- 签订日期
    start_date DATE,                                -- 生效日期
    end_date DATE,                                  -- 到期日期
    
    -- 备注
    remarks TEXT,
    
    -- 审计字段
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    
    -- 约束
    CONSTRAINT chk_amount_positive CHECK (total_amount >= 0 AND paid_amount >= 0),
    CONSTRAINT chk_paid_not_exceed_total CHECK (paid_amount <= total_amount)
);

-- 索引优化
CREATE INDEX idx_contracts_customer ON contracts(customer_id);
CREATE INDEX idx_contracts_sales ON contracts(sales_person_id);
CREATE INDEX idx_contracts_status ON contracts(status);
CREATE INDEX idx_contracts_signed_date ON contracts(signed_date);
CREATE INDEX idx_contracts_contract_number ON contracts(contract_number);
CREATE INDEX idx_contracts_file_hash ON contracts(file_hash);

-- JSONB字段GIN索引（支持快速查询合同内容）
CREATE INDEX idx_contracts_data_gin ON contracts USING GIN (contract_data);

-- 特定字段索引（加速常见查询）
CREATE INDEX idx_contracts_party_b_name ON contracts ((contract_data->>'party_b_name'));
CREATE INDEX idx_contracts_license_plate ON contracts ((contract_data->'service_content'->>'license_plate'));

-- 全文搜索索引（支持自然语言检索合同内容）
ALTER TABLE contracts ADD COLUMN search_vector tsvector;
CREATE INDEX idx_contracts_search ON contracts USING GIN (search_vector);

-- 触发器：自动更新全文搜索索引
CREATE OR REPLACE FUNCTION contracts_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('chinese', 
        COALESCE(NEW.title, '') || ' ' || 
        COALESCE(NEW.contract_number, '') || ' ' ||
        COALESCE(NEW.contract_data::text, '') || ' ' ||
        COALESCE(NEW.remarks, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE ON contracts
FOR EACH ROW EXECUTE FUNCTION contracts_search_trigger();
```

**contract_data JSONB字段设计原则：**
1. **灵活性**：不同业务类型的合同可能有不同字段（如车牌过户 vs 车辆买卖）
2. **可查询性**：使用GIN索引支持快速JSON查询
3. **版本兼容**：未来新增字段不影响旧数据
4. **AI友好**：LLM可以直接输出JSON格式，无需复杂转换

#### 3.2.4 付款表 (payments) ⭐ 核心表（支持多币种）

```sql
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    
    -- 关联合同
    contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    
    -- 付款期数信息
    installment_number INTEGER NOT NULL,            -- 第几期（1, 2, 3...）
    installment_name VARCHAR(50),                   -- 期数名称（如"定金"、"第一期款"、"尾款"）
    
    -- 金额与币种 ⭐ 新增
    currency VARCHAR(3) NOT NULL DEFAULT 'CNY',     -- 付款币种: CNY/HKD/USD
    amount DECIMAL(15, 2) NOT NULL,                 -- 本期应付金额（原始币种）
    paid_amount DECIMAL(15, 2) DEFAULT 0,           -- 实际已付金额（原始币种，支持部分付款）
    
    -- 汇率结算 ⭐ 新增关键字段
    exchange_rate DECIMAL(10, 6),                   -- 使用的汇率（1 foreign = ? CNY）
    amount_in_cny DECIMAL(15, 2) GENERATED ALWAYS AS (amount * COALESCE(exchange_rate, 1)) STORED,  -- 折算CNY金额
    paid_amount_in_cny DECIMAL(15, 2) GENERATED ALWAYS AS (paid_amount * COALESCE(exchange_rate, 1)) STORED,  -- 已付折算CNY
    
    -- 时间
    due_date DATE,                                  -- 应付款日期
    paid_date DATE,                                 -- 实际付款日期（用于查询当日汇率）
    
    -- 付款凭证
    receipt_image_path VARCHAR(500),                -- 付款凭证图片相对路径
    receipt_file_hash VARCHAR(64),                  -- 凭证文件SHA256哈希
    receipt_ocr_text TEXT,                          -- OCR识别的文本内容（用于搜索）
    
    -- 付款方式
    payment_method VARCHAR(20),
    -- 枚举值: bank_transfer(银行转账), wechat(微信), alipay(支付宝), cash(现金), check(支票)
    
    -- 状态
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- 枚举值: pending(待支付), partial(部分支付), paid(已支付), overdue(逾期), cancelled(取消)
    
    -- 来源标记
    source VARCHAR(20) DEFAULT 'manual',
    -- 枚举值: manual(手动录入), screenshot(微信截图), upload(凭证上传)
    
    -- 备注
    notes TEXT,
    
    -- 审计
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    
    -- 约束
    CONSTRAINT chk_payment_amount_positive CHECK (amount > 0),
    CONSTRAINT chk_paid_not_exceed_amount CHECK (paid_amount <= amount),
    UNIQUE (contract_id, installment_number)        -- 同一合同同一期数唯一
);

-- 索引
CREATE INDEX idx_payments_contract ON payments(contract_id);
CREATE INDEX idx_payments_due_date ON payments(due_date);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_installment ON payments(contract_id, installment_number);
CREATE INDEX idx_payments_source ON payments(source);
CREATE INDEX idx_payments_currency ON payments(currency);

-- 全文搜索（OCR文本）
ALTER TABLE payments ADD COLUMN search_vector tsvector;
CREATE INDEX idx_payments_search ON payments USING GIN (search_vector);

CREATE OR REPLACE FUNCTION payments_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('chinese', 
        COALESCE(NEW.installment_name, '') || ' ' ||
        COALESCE(NEW.receipt_ocr_text, '') || ' ' ||
        COALESCE(NEW.notes, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvectorupdate_payments BEFORE INSERT OR UPDATE ON payments
FOR EACH ROW EXECUTE FUNCTION payments_search_trigger();
```

**字段说明：**
- `currency`: 付款币种，默认CNY。每次付款可以是不同币种
- `exchange_rate`: **关键** - 付款登记时根据`paid_date`自动查询当日汇率并固化保存
- `amount_in_cny`: 自动生成列，统一折算为CNY口径便于统计
- `paid_amount_in_cny`: 自动生成列，已付金额的CNY口径

**业务逻辑示例：**
```
场景：合同总额235,000 HKD，分3期付款

第1期：20,000 HKD，付款日期2026-05-25
  → 查询2026-05-25汇率：0.92
  → amount_in_cny = 20,000 × 0.92 = 18,400 CNY

第2期：100,000 CNY，付款日期2026-06-25  
  → 汇率：1.0（CNY兑CNY）
  → amount_in_cny = 100,000 × 1.0 = 100,000 CNY

第3期：115,000 HKD，付款日期2026-07-25
  → 查询2026-07-25汇率：0.93
  → amount_in_cny = 115,000 × 0.93 = 106,950 CNY

总计已付（CNY口径）：18,400 + 100,000 + 106,950 = 225,350 CNY
合同总额（CNY口径）：235,000 × 0.93 = 218,550 CNY（按最后一期汇率）
剩余尾款：218,550 - 225,350 = -6,800 CNY（已超额支付）
```

#### 3.2.5 汇率表 (exchange_rates) ⭐ 新增核心表

```sql
CREATE TABLE exchange_rates (
    id SERIAL PRIMARY KEY,
    
    -- 汇率信息
    from_currency VARCHAR(3) NOT NULL,              -- 源币种（HKD/USD等）
    to_currency VARCHAR(3) NOT NULL DEFAULT 'CNY',  -- 目标币种（默认CNY）
    rate DECIMAL(10, 6) NOT NULL,                   -- 汇率（1 HKD = ? CNY）
    
    -- 汇率日期
    rate_date DATE NOT NULL,                        -- 汇率生效日期
    
    -- 数据来源
    source VARCHAR(20) DEFAULT 'manual',            -- 来源: manual(手动录入), api(自动获取), system(系统默认)
    
    -- 是否启用
    is_active BOOLEAN DEFAULT TRUE,                 -- 是否启用（支持历史汇率回溯）
    
    -- 备注
    remarks TEXT,                                   -- 备注（如"中国人民银行中间价"）
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    
    -- 约束
    UNIQUE (from_currency, to_currency, rate_date)  -- 同一天同一币种对唯一
);

-- 索引
CREATE INDEX idx_exchange_rates_currencies ON exchange_rates(from_currency, to_currency);
CREATE INDEX idx_exchange_rates_date ON exchange_rates(rate_date DESC);
CREATE INDEX idx_exchange_rates_active ON exchange_rates(is_active);

-- 初始数据示例（需要根据实际汇率更新）
INSERT INTO exchange_rates (from_currency, to_currency, rate, rate_date, source, remarks) VALUES
('HKD', 'CNY', 0.920000, '2026-05-25', 'system', '系统默认汇率'),
('USD', 'CNY', 7.250000, '2026-05-25', 'system', '系统默认汇率');
```

**字段说明：**
- `rate`: 汇率精度6位小数，保证计算准确性
- `rate_date`: 支持历史汇率查询，用于追溯付款时的实际汇率
- `is_active`: 支持汇率版本管理，保留历史记录
- **业务规则**：付款登记时，根据`paid_date`自动查询当日汇率；如果当日无数据，向前查找最近的汇率

**使用示例：**
```sql
-- 查询2026-05-25的HKD兑CNY汇率
SELECT rate FROM exchange_rates 
WHERE from_currency = 'HKD' AND to_currency = 'CNY' 
  AND rate_date <= '2026-05-25' AND is_active = TRUE
ORDER BY rate_date DESC LIMIT 1;

-- 结果：0.920000（表示1 HKD = 0.92 CNY）
```

#### 3.2.6 文件元数据表 (files)

```sql
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    
    -- 文件信息
    original_filename VARCHAR(500) NOT NULL,        -- 原始文件名
    stored_filename VARCHAR(500) NOT NULL,          -- 存储文件名（UUID或哈希）
    file_path VARCHAR(500) NOT NULL,                -- 相对路径（相对于data/目录）
    file_size BIGINT NOT NULL,                      -- 文件大小（字节）
    mime_type VARCHAR(100),                         -- MIME类型
    file_hash VARCHAR(64) NOT NULL,                 -- SHA256哈希
    
    -- 关联业务
    related_type VARCHAR(20) NOT NULL,              -- 关联类型: contract/receipt/screenshot
    related_id INTEGER NOT NULL,                    -- 关联的合同ID或付款ID
    
    -- OCR结果（如果适用）
    ocr_text TEXT,                                  -- OCR提取的文本
    ocr_confidence DECIMAL(5, 4),                   -- OCR置信度（0-1）
    
    -- AI识别结果（微信截图专用）
    ai_extracted_data JSONB DEFAULT '{}',
    /*
    ai_extracted_data 示例（微信截图）：
    {
        "group_name": "华星-卢灿梅-车牌过户服务群",
        "recognized_text": "张三于2026年5月25日转账20000元",
        "entities": {
            "customer_name": "张三",
            "amount": 20000,
            "date": "2026-05-25",
            "action": "transfer"
        },
        "confidence": 0.92
    }
    */
    
    -- 上传者
    uploaded_by INTEGER REFERENCES users(id),
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 约束
    UNIQUE (file_hash, related_type, related_id)    -- 防止重复上传
);

-- 索引
CREATE INDEX idx_files_related ON files(related_type, related_id);
CREATE INDEX idx_files_hash ON files(file_hash);
CREATE INDEX idx_files_uploaded_by ON files(uploaded_by);
CREATE INDEX idx_files_ocr_text ON files USING GIN (to_tsvector('chinese', ocr_text));
```

#### 3.2.6 操作日志表 (audit_logs)

```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(50) NOT NULL,                    -- 操作类型: create/update/delete/upload/login
    entity_type VARCHAR(50) NOT NULL,               -- 实体类型: customer/contract/payment/file
    entity_id INTEGER,                              -- 实体ID
    old_values JSONB,                               -- 修改前的值
    new_values JSONB,                               -- 修改后的值
    ip_address INET,                                -- IP地址
    user_agent TEXT,                                -- User-Agent
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_action ON audit_logs(action);
```

#### 3.2.7 对话历史表 (chat_history)

```sql
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id VARCHAR(100),                        -- 会话ID（保持上下文）
    question TEXT NOT NULL,                         -- 用户问题
    answer TEXT,                                    -- AI回答
    context_contracts INTEGER[],                    -- 参考的合同ID列表
    intent_type VARCHAR(50),                        -- 意图类型: query_balance/query_contract/statistics
    extracted_entities JSONB,                       -- 提取的实体: {"customer_name": "张三"}
    sql_query TEXT,                                 -- 生成的SQL查询（用于调试）
    llm_model VARCHAR(50),                          -- 使用的模型
    tokens_used INTEGER,                            -- 消耗的token数
    confidence DECIMAL(5, 4),                       -- 回答置信度
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_chat_user ON chat_history(user_id);
CREATE INDEX idx_chat_session ON chat_history(session_id);
CREATE INDEX idx_chat_created ON chat_history(created_at DESC);
```

---

## 4️⃣ API接口规范

### 4.1 基础约定

#### 4.1.1 Base URL
```
开发环境: http://localhost:8000/api/v1
生产环境: https://api.huaxing.com/api/v1
```

#### 4.1.2 统一响应格式

**成功响应：**
```json
{
  "code": 200,
  "message": "success",
  "data": { ... },
  "timestamp": "2026-05-25T10:30:00Z"
}
```

**错误响应：**
```json
{
  "code": 400,
  "message": "参数错误: customer_name不能为空",
  "error_details": {
    "field": "customer_name",
    "error": "required"
  },
  "timestamp": "2026-05-25T10:30:00Z"
}
```

**分页响应：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [...],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 100,
      "total_pages": 5
    }
  },
  "timestamp": "2026-05-25T10:30:00Z"
}
```

#### 4.1.3 HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未授权（token无效/过期） |
| 403 | 禁止访问（权限不足） |
| 404 | 资源不存在 |
| 409 | 冲突（如重复数据） |
| 500 | 服务器内部错误 |

#### 4.1.4 认证方式

所有需要认证的接口必须在Header中携带JWT token：
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 4.2 认证模块

#### POST /auth/login
登录获取access_token

**请求：**
```json
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "zhangsan",
  "password": "password123"
}
```

**响应：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 3600,
    "user": {
      "id": 1,
      "username": "zhangsan",
      "full_name": "张三",
      "email": "zhangsan@huaxing.com",
      "role": "sales"
    }
  }
}
```

#### POST /auth/refresh
刷新access_token

**请求：**
```json
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**响应：**
```json
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 3600
  }
}
```

#### GET /auth/me
获取当前用户信息

**响应：**
```json
{
  "code": 200,
  "data": {
    "id": 1,
    "username": "zhangsan",
    "full_name": "张三",
    "email": "zhangsan@huaxing.com",
    "role": "sales",
    "department": "业务部",
    "last_login_at": "2026-05-25T10:00:00Z"
  }
}
```

### 4.3 客户管理模块

#### GET /customers
获取客户列表

**查询参数：**
- `page`: 页码（默认1）
- `per_page`: 每页数量（默认20，最大100）
- `keyword`: 搜索关键词（客户名/电话/邮箱）
- `sort_by`: 排序字段（created_at/name）
- `order`: 排序方向（asc/desc）

**响应：**
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "name": "卢灿梅",
        "contact_person": null,
        "phone": "13800138000",
        "email": null,
        "wechat_group_name": "华星-卢灿梅-车牌过户服务群",
        "created_at": "2026-05-25T10:00:00Z",
        "contract_count": 2,
        "total_contract_amount": 470000
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 50
    }
  }
}
```

#### POST /customers
创建客户

**请求：**
```json
POST /api/v1/customers
Content-Type: application/json
Authorization: Bearer {token}

{
  "name": "深圳市XX科技有限公司",
  "contact_person": "李四",
  "phone": "13800138000",
  "email": "lisi@example.com",
  "address": "深圳市南山区科技园",
  "wechat_group_name": "华星-深圳XX科技-车辆服务群",
  "remarks": "重要客户"
}
```

**响应：**
```json
{
  "code": 201,
  "message": "客户创建成功",
  "data": {
    "id": 2,
    "name": "深圳市XX科技有限公司",
    ...
  }
}
```

#### GET /customers/{id}
获取客户详情

**响应：**
```json
{
  "code": 200,
  "data": {
    "id": 1,
    "name": "卢灿梅",
    "contact_person": null,
    "phone": "13800138000",
    "email": null,
    "wechat_group_name": "华星-卢灿梅-车牌过户服务群",
    "address": null,
    "remarks": null,
    "created_at": "2026-05-25T10:00:00Z",
    "updated_at": "2026-05-25T10:00:00Z",
    "contracts": [
      {
        "id": 1,
        "contract_number": "HT20260525001",
        "title": "两地车牌指标过户服务合约",
        "total_amount": 235000,
        "paid_amount": 20000,
        "remaining_amount": 215000,
        "status": "active",
        "signed_date": "2026-05-25"
      }
    ]
  }
}
```

### 4.4 合同管理模块

#### POST /contracts/upload-and-parse  核心接口
上传合同并启动AI解析

**请求：**
```
POST /api/v1/contracts/upload-and-parse
Content-Type: multipart/form-data
Authorization: Bearer {token}

Form Data:
- file: <合同图片/PDF文件>
- customer_id: 1 (可选，如果已知客户)
- auto_create_customer: true (可选，如果客户不存在则自动创建)
```

**响应（立即返回）：**
```json
{
  "code": 202,
  "message": "合同上传成功，正在AI解析中",
  "data": {
    "contract_id": 1,
    "task_id": "abc-123-def-456",
    "status": "parsing",
    "estimated_time_seconds": 15
  }
}
```

**说明：**
- 此接口为异步接口，立即返回task_id
- 前端需轮询 `/contracts/parse-status/{task_id}` 获取解析结果

#### GET /contracts/parse-status/{task_id}
查询合同解析状态

**响应（解析中）：**
```json
{
  "code": 200,
  "data": {
    "task_id": "abc-123-def-456",
    "status": "processing",
    "progress": 60,
    "message": "正在调用AI解析合同内容..."
  }
}
```

**响应（解析完成）：**
```json
{
  "code": 200,
  "data": {
    "task_id": "abc-123-def-456",
    "status": "completed",
    "contract_id": 1,
    "parsed_data": {
      "party_a": {
        "name": "华星智源开发有限公司",
        "contact": "98702065"
      },
      "party_b": {
        "name": "卢灿梅",
        "id_type": "身份证",
        "id_number": "M60390A(7)"
      },
      "service_content": {
        "license_plate": "粤ZS629港",
        "port": "莲塘口岸"
      },
      "payment_terms": [
        {"type": "deposit", "name": "定金", "amount": 20000},
        {"type": "final", "name": "尾款", "amount": 215000}
      ],
      "total_amount": 235000,
      "signed_date": "2026-05-25"
    },
    "confidence": 0.92,
    "needs_review": false,
    "warnings": []
  }
}
```

**响应（解析失败）：**
```json
{
  "code": 200,
  "data": {
    "task_id": "abc-123-def-456",
    "status": "failed",
    "error_code": "OCR_FAILED",
    "error_message": "图片清晰度不足，无法识别文字",
    "suggestion": "请上传更清晰的图片或PDF扫描件"
  }
}
```

#### POST /contracts/{id}/confirm-parsed-data
确认或修正AI解析结果

**请求：**
```json
POST /api/v1/contracts/1/confirm-parsed-data
Content-Type: application/json
Authorization: Bearer {token}

{
  "contract_data": {
    "party_a": {...},
    "party_b": {...},
    ...
  },
  "manual_corrections": ["party_b.id_number", "total_amount"],
  "notes": "修正了身份证号和总金额"
}
```

**响应：**
```json
{
  "code": 200,
  "message": "合同数据确认成功",
  "data": {
    "id": 1,
    "contract_number": "HT20260525001",
    "status": "active",
    "contract_data": {...}
  }
}
```

#### GET /contracts
获取合同列表

**查询参数：**
- `page`: 页码
- `per_page`: 每页数量
- `status`: 合同状态（draft/active/completed/cancelled）
- `customer_id`: 客户ID
- `customer_name`: 客户名称（模糊搜索）
- `keyword`: 全文搜索关键词
- `date_from`: 签订日期起始
- `date_to`: 签订日期结束
- `sort_by`: 排序字段
- `order`: 排序方向

**响应：**
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "contract_number": "HT20260525001",
        "title": "两地车牌指标过户服务合约",
        "customer_name": "卢灿梅",
        "total_amount": 235000,
        "paid_amount": 20000,
        "remaining_amount": 215000,
        "status": "active",
        "signed_date": "2026-05-25",
        "created_at": "2026-05-25T10:30:00Z",
        "has_unpaid_overdue": false
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 50
    }
  }
}
```

#### GET /contracts/{id}
获取合同详情

**响应：**
```json
{
  "code": 200,
  "data": {
    "id": 1,
    "contract_number": "HT20260525001",
    "title": "两地车牌指标过户服务合约",
    "customer": {
      "id": 1,
      "name": "卢灿梅",
      "phone": "13800138000"
    },
    "sales_person": {
      "id": 1,
      "full_name": "张三"
    },
    "contract_data": {
      "party_a": {...},
      "party_b": {...},
      "service_content": {...},
      "payment_terms": [...]
    },
    "total_amount": 235000,
    "paid_amount": 20000,
    "remaining_amount": 215000,
    "status": "active",
    "signed_date": "2026-05-25",
    "payments": [
      {
        "id": 1,
        "installment_number": 1,
        "installment_name": "定金",
        "amount": 20000,
        "paid_amount": 20000,
        "status": "paid",
        "paid_date": "2026-05-25",
        "receipt_image_url": "/api/v1/files/123/download"
      }
    ],
    "files": [
      {
        "id": 1,
        "original_filename": "两地牌指标过户服务合约01.png",
        "file_type": "contract",
        "uploaded_at": "2026-05-25T10:30:00Z"
      }
    ],
    "created_at": "2026-05-25T10:30:00Z",
    "updated_at": "2026-05-25T10:30:00Z"
  }
}
```

### 4.5 付款管理模块

#### POST /contracts/{id}/payment-plan
创建多期付款计划

**请求：**
```json
POST /api/v1/contracts/1/payment-plan
Content-Type: application/json
Authorization: Bearer {token}

{
  "installments": [
    {
      "installment_number": 1,
      "installment_name": "定金",
      "amount": 20000,
      "due_date": "2026-05-25"
    },
    {
      "installment_number": 2,
      "installment_name": "第一期款",
      "amount": 100000,
      "due_date": "2026-06-25"
    },
    {
      "installment_number": 3,
      "installment_name": "尾款",
      "amount": 115000,
      "due_date": "2026-07-25"
    }
  ]
}
```

**响应：**
```json
{
  "code": 201,
  "message": "付款计划创建成功",
  "data": {
    "contract_id": 1,
    "installments_created": 3,
    "total_amount": 235000,
    "payments": [
      {"id": 1, "installment_number": 1, ...},
      {"id": 2, "installment_number": 2, ...},
      {"id": 3, "installment_number": 3, ...}
    ]
  }
}
```

#### POST /payments/upload-receipt  核心接口
上传付款凭证并自动识别

**请求：**
```
POST /api/v1/payments/upload-receipt
Content-Type: multipart/form-data
Authorization: Bearer {token}

Form Data:
- contract_id: 1
- installment_number: 2 (可选，如果不指定则创建新的付款记录)
- file: <付款凭证图片>
- paid_amount: 100000 (可选，AI会自动识别)
- paid_date: "2026-06-25" (可选，AI会自动识别)
- payment_method: "bank_transfer"
- notes: "工商银行转账"
```

**响应：**
```json
{
  "code": 201,
  "message": "付款凭证上传成功",
  "data": {
    "payment_id": 2,
    "status": "paid",
    "receipt_ocr_result": {
      "recognized_amount": 100000,
      "recognized_date": "2026-06-25",
      "bank_name": "中国工商银行",
      "confidence": 0.95
    },
    "contract_status": {
      "total_amount": 235000,
      "paid_amount": 120000,
      "remaining_amount": 115000,
      "is_completed": false
    }
  }
}
```

#### GET /contracts/{id}/payments
获取合同的付款记录

**响应：**
```json
{
  "code": 200,
  "data": {
    "contract_id": 1,
    "contract_number": "HT20260525001",
    "total_amount": 235000,
    "paid_amount": 120000,
    "remaining_amount": 115000,
    "completion_rate": 51.06,
    "payments": [
      {
        "id": 1,
        "installment_number": 1,
        "installment_name": "定金",
        "amount": 20000,
        "paid_amount": 20000,
        "due_date": "2026-05-25",
        "paid_date": "2026-05-25",
        "status": "paid",
        "payment_method": "bank_transfer",
        "receipt_image_url": "/api/v1/files/123/download",
        "created_at": "2026-05-25T10:30:00Z"
      },
      {
        "id": 2,
        "installment_number": 2,
        "installment_name": "第一期款",
        "amount": 100000,
        "paid_amount": 100000,
        "due_date": "2026-06-25",
        "paid_date": "2026-06-25",
        "status": "paid",
        "payment_method": "bank_transfer",
        "receipt_image_url": "/api/v1/files/124/download",
        "created_at": "2026-06-25T14:20:00Z"
      },
      {
        "id": 3,
        "installment_number": 3,
        "installment_name": "尾款",
        "amount": 115000,
        "paid_amount": 0,
        "due_date": "2026-07-25",
        "paid_date": null,
        "status": "pending",
        "is_overdue": false,
        "days_until_due": 30
      }
    ]
  }
}
```

### 4.6 智能问答模块

#### POST /agent/chat  核心接口
发起智能问答

**请求：**
```json
POST /api/v1/agent/chat
Content-Type: application/json
Authorization: Bearer {token}

{
  "question": "张三还欠多少钱？",
  "session_id": "sess-123",
  "context_filters": {
    "customer_name": "张三",
    "status": "active"
  }
}
```

**响应：**
```json
{
  "code": 200,
  "data": {
    "answer": "根据系统记录，客户张三（卢灿梅）目前还有1笔尾款未支付，金额为115,000元，应于2026年7月25日前支付。目前已支付定金20,000元和第一期款100,000元，总计已支付120,000元，占合同总额235,000元的51.06%。",
    "sources": [
      {
        "type": "contract",
        "contract_id": 1,
        "contract_number": "HT20260525001",
        "relevance_score": 0.98
      },
      {
        "type": "payment",
        "payment_id": 3,
        "installment_name": "尾款",
        "relevance_score": 0.95
      }
    ],
    "session_id": "sess-123",
    "tokens_used": 180,
    "confidence": 0.96,
    "intent": {
      "type": "query_remaining_balance",
      "extracted_entities": {
        "customer_name": "张三"
      }
    }
  }
}
```

**更多问答示例：**

**示例1：查询客户所有合同**
```
问："张三有哪些合同？"
答："客户张三（卢灿梅）共有2份合同：
1. HT20260525001 - 两地车牌指标过户服务合约，金额235,000元，状态：执行中
2. HT20260420002 - 车辆买卖合同，金额180,000元，状态：已完成"
```

**示例2：统计查询**
```
问："上个月签了多少合同？总金额多少？"
答："2026年4月共签订5份合同，总金额为1,250,000元。其中：
- 车牌过户服务：3份，金额650,000元
- 车辆买卖：2份，金额600,000元"
```

**示例3：逾期查询**
```
问："有哪些逾期未付的尾款？"
答："目前有2笔逾期未付款项：
1. 客户李四 - HT20260315003，第二期款50,000元，逾期15天
2. 客户王五 - HT20260401005，尾款80,000元，逾期5天"
```

### 4.7 文件管理模块

#### GET /files/{id}/download
下载文件

**响应：**
- Content-Type: 根据文件类型动态设置
- Content-Disposition: attachment; filename="原文件名"
- Body: 文件二进制流

#### DELETE /files/{id}
删除文件（软删除，仅标记deleted_at）

**响应：**
```json
{
  "code": 200,
  "message": "文件删除成功"
}
```

---

## 5️⃣ AI集成方案

### 5.1 SiliconFlow API配置

#### 环境变量
```bash
# .env
SILICONFLOW_API_KEY=sk-modiwmwfcvwlgxgotwlkxhtxxjufxwbfgdxssyvjqiaczpkl
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1

# 视觉模型（合同/凭证解析）
SILICONFLOW_VISION_MODEL=Qwen/Qwen3-VL-32B-Instruct

# 文本模型（智能问答）
SILICONFLOW_TEXT_MODEL=Qwen/Qwen3-VL-8B-Instruct

# 可选：百炼 DeepSeek-V4-Flash Agent 推理模型（复用 DASHSCOPE_API_KEY）
DASHSCOPE_AGENT_MODEL=deepseek-v4-flash
```

### 5.2 LLM客户端封装

```python
# backend/app/ai/llm_client.py
import base64
import json
from typing import Dict, Any, Optional
import requests
from app.core.config import settings

class SiliconFlowClient:
    """SiliconFlow Qwen-VL API客户端"""
    
    def __init__(self):
        self.api_key = settings.SILICONFLOW_API_KEY
        self.base_url = settings.SILICONFLOW_BASE_URL
        self.vision_model = settings.SILICONFLOW_VISION_MODEL
        self.text_model = settings.SILICONFLOW_TEXT_MODEL
    
    def parse_contract_image(self, image_path: str) -> Dict[str, Any]:
        """
        解析合同图片，提取结构化数据
        
        Args:
            image_path: 合同图片本地路径
            
        Returns:
            {
                "data": {...},  # 解析的结构化数据
                "confidence": 0.92,
                "raw_response": "..."
            }
        """
        # 读取图片并转base64
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()
        
        # 构造请求
        payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": self._build_contract_extraction_prompt()
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4096
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 调用API
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60
        )
        
        if response.status_code != 200:
            raise Exception(f"SiliconFlow API error: {response.text}")
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # 尝试解析JSON
        try:
            structured_data = json.loads(content)
        except json.JSONDecodeError:
            # 如果返回的不是纯JSON，尝试提取JSON部分
            structured_data = self._extract_json_from_text(content)
        
        return {
            "data": structured_data,
            "confidence": self._calculate_confidence(structured_data),
            "raw_response": content,
            "tokens_used": result.get("usage", {}).get("total_tokens", 0)
        }
    
    def _build_contract_extraction_prompt(self) -> str:
        """构建合同解析Prompt"""
        return """
你是一个专业的合同信息提取助手。请仔细分析这张合同图片，提取以下关键信息并以严格的JSON格式返回：

{
  "contract_number": "合同编号（字符串）",
  "title": "合同标题（字符串）",
  "signed_date": "签订日期（YYYY-MM-DD格式）",
  "party_a": {
    "name": "甲方名称（字符串）",
    "contact": "联系方式（字符串）",
    "address": "地址（字符串，如无则为null）"
  },
  "party_b": {
    "name": "乙方姓名（字符串）",
    "id_type": "证件类型（字符串，如"身份证"）",
    "id_number": "证件号码（字符串）",
    "address": "地址（字符串，如无则为null）"
  },
  "service_content": {
    "description": "服务内容描述（字符串）",
    "license_plate": "车牌号（字符串，如无则为null）",
    "port": "通行口岸（字符串，如无则为null）",
    "old_license_plate": "原车牌号（字符串，如无则为null）",
    "new_license_plate": "新车牌号（字符串，如无则为null）"
  },
  "payment_terms": [
    {
      "type": "款项类型（deposit/final/installment）",
      "name": "款项名称（字符串，如"定金"、"尾款"）",
      "amount": 金额（数字类型）,
      "condition": "支付条件（字符串）",
      "due_date": "应付款日期（YYYY-MM-DD格式，如无则为null）"
    }
  ],
  "total_amount": 合同总金额（数字类型）,
  "contract_type": "合同类型（vehicle_license_transfer/vehicle_sale/other）",
  "special_clauses": ["特殊条款1", "特殊条款2"]
}

严格要求：
1. 只返回纯JSON，不要包含markdown格式（如```json）或其他文字说明
2. 如果某个字段无法识别，设为null
3. 金额统一转换为数字类型（不要带"元"、"￥"等单位）
4. 日期统一为YYYY-MM-DD格式
5. 数组字段如果没有内容，返回空数组[]
6. 确保JSON格式合法，可以被json.loads()解析
        """.strip()
    
    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取JSON部分"""
        import re
        
        # 尝试匹配```json ... ```格式
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # 尝试匹配第一个{到最后一个}
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        
        raise ValueError("无法从响应中提取JSON")
    
    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """计算解析置信度"""
        # 简单规则：检查关键字段是否存在
        key_fields = ["contract_number", "party_a", "party_b", "total_amount"]
        present_fields = sum(1 for field in key_fields if data.get(field))
        
        base_confidence = present_fields / len(key_fields)
        
        # 如果有payment_terms且不为空，增加置信度
        if data.get("payment_terms"):
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def answer_question(self, question: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于上下文数据回答问题
        
        Args:
            question: 用户问题
            context_data: 从数据库查询的真实数据
            
        Returns:
            {
                "answer": "自然语言回答",
                "tokens_used": 180,
                "confidence": 0.96
            }
        """
        # 构造Prompt
        prompt = f"""
你是一个专业的业务助手。请基于以下真实数据回答用户问题，不要编造任何信息。

【可用数据】
{json.dumps(context_data, ensure_ascii=False, indent=2)}

【用户问题】
{question}

【回答要求】
1. 只基于上述数据回答，如果数据中没有相关信息，明确告知用户
2. 使用自然、友好的语气
3. 保留关键数字和单位（如金额保留"元"）
4. 如果涉及多个项目，使用列表清晰展示
5. 回答长度控制在200字以内
6. 如果数据不足以回答问题，说明缺少什么信息
        """.strip()
        
        # 调用API
        payload = {
            "model": self.text_model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 512
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"SiliconFlow API error: {response.text}")
        
        result = response.json()
        answer = result["choices"][0]["message"]["content"]
        
        return {
            "answer": answer,
            "tokens_used": result.get("usage", {}).get("total_tokens", 0),
            "confidence": 0.9  # 固定置信度，因为是基于真实数据
        }
```

### 5.3 异步任务设计

```python
# backend/app/tasks/contract_tasks.py
from celery import Celery
from app.ai.llm_client import SiliconFlowClient
from app.models.contract import Contract
from app.db.session import SessionLocal

celery_app = Celery('tasks', broker='redis://localhost:6379/0')

@celery_app.task(bind=True, max_retries=3)
def parse_contract_task(self, contract_id: int, file_path: str):
    """
    异步解析合同
    
    Args:
        contract_id: 合同ID
        file_path: 合同文件本地路径
    """
    db = SessionLocal()
    try:
        # 获取合同记录
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return {"error": "Contract not found"}
        
        # 调用AI解析
        client = SiliconFlowClient()
        result = client.parse_contract_image(file_path)
        
        # 更新合同数据
        contract.contract_data = result["data"]
        contract.confidence = result["confidence"]
        
        # 判断是否需要人工审核
        if result["confidence"] < 0.85:
            contract.status = "pending_review"
            contract.needs_review = True
        else:
            contract.status = "active"
        
        db.commit()
        
        return {
            "contract_id": contract_id,
            "status": "completed",
            "confidence": result["confidence"],
            "needs_review": contract.needs_review
        }
        
    except Exception as exc:
        # 重试逻辑
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
```

---

## 6️⃣ 汇率管理模块 ⭐ 新增核心模块

### 6.1 业务需求

**场景描述：**
- 合同金额币种：CNY（人民币）或 HKD（港币）
- 付款币种：每次付款可以是 CNY 或 HKD（不同期次可能不同）
- **汇率结算规则**：按**付款登记时**的实时汇率折算为CNY
- **统计口径**：统一折算成CNY进行汇总和报表

**示例：**
```
合同总额：235,000 HKD（签订日期：2026-05-25）

第1期付款：20,000 HKD，付款日期：2026-05-25
  → 查询2026-05-25汇率：1 HKD = 0.92 CNY
  → 折算CNY：20,000 × 0.92 = 18,400 CNY

第2期付款：100,000 CNY，付款日期：2026-06-25
  → 汇率：1.0（CNY兑CNY）
  → 折算CNY：100,000 × 1.0 = 100,000 CNY

第3期付款：115,000 HKD，付款日期：2026-07-25
  → 查询2026-07-25汇率：1 HKD = 0.93 CNY
  → 折算CNY：115,000 × 0.93 = 106,950 CNY

总计已付（CNY口径）：18,400 + 100,000 + 106,950 = 225,350 CNY
```

### 6.2 汇率服务实现

```python
# backend/app/services/exchange_rate_service.py
from decimal import Decimal
from datetime import date, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models.exchange_rate import ExchangeRate

class ExchangeRateService:
    """汇率管理服务"""
    
    @staticmethod
    def get_exchange_rate(
        db: Session,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Optional[Decimal]:
        """
        获取指定日期的汇率
        
        Args:
            from_currency: 源币种（HKD/USD等）
            to_currency: 目标币种（默认CNY）
            rate_date: 汇率日期
            
        Returns:
            汇率值，如果找不到则返回None
            
        逻辑：
        1. 优先查找rate_date当天的汇率
        2. 如果当天没有，向前查找最近的汇率（最多回溯30天）
        3. 如果还是没有，返回系统默认汇率
        """
        # 同币种直接返回1.0
        if from_currency == to_currency:
            return Decimal('1.0')
        
        # 查询当日或最近30天内的汇率
        start_date = rate_date - timedelta(days=30)
        
        rate_record = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.rate_date >= start_date,
            ExchangeRate.rate_date <= rate_date,
            ExchangeRate.is_active == True
        ).order_by(
            ExchangeRate.rate_date.desc()
        ).first()
        
        if rate_record:
            return rate_record.rate
        
        # 如果找不到历史汇率，使用系统默认汇率（最近一条is_active=True的记录）
        default_rate = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.source == 'system',
            ExchangeRate.is_active == True
        ).order_by(
            ExchangeRate.rate_date.desc()
        ).first()
        
        if default_rate:
            return default_rate.rate
        
        # 最后的兜底：返回硬编码的参考汇率
        fallback_rates = {
            ('HKD', 'CNY'): Decimal('0.92'),
            ('USD', 'CNY'): Decimal('7.25'),
        }
        
        return fallback_rates.get((from_currency, to_currency))
    
    @staticmethod
    def convert_to_cny(
        db: Session,
        amount: Decimal,
        from_currency: str,
        rate_date: date
    ) -> tuple[Decimal, Decimal]:
        """
        将金额转换为CNY
        
        Args:
            amount: 原始金额
            from_currency: 原始币种
            rate_date: 汇率日期
            
        Returns:
            (汇率, 折算后CNY金额)
        """
        exchange_rate = ExchangeRateService.get_exchange_rate(
            db, from_currency, 'CNY', rate_date
        )
        
        if exchange_rate is None:
            raise ValueError(f"无法获取 {from_currency} 兑 CNY 的汇率（日期：{rate_date}）")
        
        amount_in_cny = amount * exchange_rate
        
        return exchange_rate, amount_in_cny
    
    @staticmethod
    def update_exchange_rate(
        db: Session,
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        rate_date: date,
        source: str = 'manual',
        created_by: int = None
    ):
        """
        更新或创建汇率记录
        
        Args:
            from_currency: 源币种
            to_currency: 目标币种
            rate: 汇率值
            rate_date: 汇率日期
            source: 来源（manual/api/system）
            created_by: 创建者ID
        """
        # 检查是否已存在
        existing = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.rate_date == rate_date
        ).first()
        
        if existing:
            # 更新现有记录
            existing.rate = rate
            existing.source = source
            existing.is_active = True
        else:
            # 创建新记录
            new_rate = ExchangeRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                rate_date=rate_date,
                source=source,
                is_active=True,
                created_by=created_by
            )
            db.add(new_rate)
        
        db.commit()
```

### 6.3 付款服务集成汇率

```python
# backend/app/services/payment_service.py
from app.services.exchange_rate_service import ExchangeRateService

class PaymentService:
    """付款服务"""
    
    @staticmethod
    def create_payment_with_exchange_rate(
        db: Session,
        contract_id: int,
        installment_number: int,
        currency: str,
        amount: Decimal,
        paid_date: date,
        payment_method: str,
        receipt_image_path: str = None,
        created_by: int = None
    ):
        """
        创建付款记录并自动计算汇率
        
        Args:
            contract_id: 合同ID
            installment_number: 期数
            currency: 付款币种（CNY/HKD）
            amount: 付款金额（原始币种）
            paid_date: 付款日期（用于查询汇率）
            payment_method: 付款方式
            receipt_image_path: 凭证图片路径
            created_by: 创建者ID
            
        Returns:
            创建的付款记录
        """
        from app.models.payment import Payment
        from app.models.contract import Contract
        
        # 获取合同信息
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"合同不存在：{contract_id}")
        
        # 计算汇率和折算金额
        exchange_rate, amount_in_cny = ExchangeRateService.convert_to_cny(
            db, amount, currency, paid_date
        )
        
        # 创建付款记录
        payment = Payment(
            contract_id=contract_id,
            installment_number=installment_number,
            currency=currency,
            amount=amount,
            paid_amount=amount,  # 全额支付
            exchange_rate=exchange_rate,
            paid_date=paid_date,
            payment_method=payment_method,
            receipt_image_path=receipt_image_path,
            status='paid',
            created_by=created_by
        )
        
        db.add(payment)
        
        # 更新合同的已付金额（同时更新原始币种和CNY口径）
        if currency == contract.currency:
            # 同币种直接累加
            contract.paid_amount += amount
        else:
            # 不同币种，需要按当前汇率折算后累加到CNY口径
            # 这里简化处理，实际应该更复杂
            pass
        
        contract.paid_amount_in_cny += amount_in_cny
        
        # 判断是否已完成
        if contract.paid_amount_in_cny >= contract.total_amount_in_cny:
            contract.status = 'completed'
        
        db.commit()
        db.refresh(payment)
        
        return payment
```

### 6.4 API接口设计

#### GET /exchange-rates/latest
获取最新汇率

**请求：**
```
GET /api/v1/exchange-rates/latest?from=HKD&to=CNY
```

**响应：**
```json
{
  "code": 200,
  "data": {
    "from_currency": "HKD",
    "to_currency": "CNY",
    "rate": 0.920000,
    "rate_date": "2026-05-25",
    "source": "system"
  }
}
```

#### POST /exchange-rates
手动录入汇率（管理员权限）

**请求：**
```json
POST /api/v1/exchange-rates
Content-Type: application/json
Authorization: Bearer {token}

{
  "from_currency": "HKD",
  "to_currency": "CNY",
  "rate": 0.930000,
  "rate_date": "2026-07-25",
  "source": "manual",
  "remarks": "中国人民银行中间价"
}
```

**响应：**
```json
{
  "code": 201,
  "message": "汇率录入成功",
  "data": {
    "id": 5,
    "from_currency": "HKD",
    "to_currency": "CNY",
    "rate": 0.930000,
    "rate_date": "2026-07-25",
    "source": "manual"
  }
}
```

### 6.5 汇率数据来源

**推荐方案：**
1. **一期（MVP）**：手动录入 + 系统默认汇率
   - 管理员定期从中国人民银行官网查询汇率并手动录入
   - 设置合理的默认汇率作为兜底

2. **二期（自动化）**：对接汇率API自动同步
   - 推荐API：
     - [中国外汇交易中心](http://www.chinamoney.com.cn/)
     - 阿里云汇率API
     - ExchangeRate-API（国际）
   - 每日凌晨自动拉取并更新数据库

3. **三期（高级）**：实时汇率 + 历史趋势
   - 支持汇率波动预警
   - 提供汇率历史曲线图

---

## 7️ 文件存储方案

### 6.1 目录结构

```
/data/contract-system/
── contracts/                          # 合同原件
│   └── {year}/{month}/
│       └── contract_{contract_number}_{timestamp}_{uuid}.{ext}
│       示例: contract_HT20260525001_20260525103000_abc123.pdf
│
├── receipts/                           # 付款凭证
│   ── {year}/{month}/
│       └── receipt_pay{payment_id}_{timestamp}_{uuid}.{ext}
│       示例: receipt_pay2_20260625142000_def456.jpg
│
├── screenshots/                        # 微信截图
│   └── {year}/{month}/
│       └── screenshot_{timestamp}_{uuid}.{ext}
│       示例: screenshot_20260525150000_ghi789.jpg
│
└── temp/                               # 临时文件（解析中）
    └── upload_{timestamp}_{uuid}.{ext}
```

### 6.2 文件命名规则

```python
# backend/app/utils/file_utils.py
import os
import uuid
import hashlib
from datetime import datetime
from pathlib import Path

def generate_contract_filename(contract_number: str, ext: str) -> str:
    """生成合同文件名"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:6]
    return f"contract_{contract_number}_{timestamp}_{unique_id}.{ext}"

def generate_receipt_filename(payment_id: int, ext: str) -> str:
    """生成付款凭证文件名"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:6]
    return f"receipt_pay{payment_id}_{timestamp}_{unique_id}.{ext}"

def save_uploaded_file(file, base_dir: str, filename: str) -> tuple[str, str]:
    """
    保存上传文件
    
    Returns:
        (relative_path, file_hash)
    """
    # 创建目录
    year_month = datetime.now().strftime("%Y/%m")
    target_dir = Path(base_dir) / year_month
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存文件
    file_path = target_dir / filename
    with open(file_path, "wb") as f:
        content = file.read()
        f.write(content)
    
    # 计算哈希
    file_hash = hashlib.sha256(content).hexdigest()
    
    # 返回相对路径
    relative_path = str(Path(year_month) / filename)
    
    return relative_path, file_hash
```

---

## 7️⃣ 权限控制方案

### 7.1 RBAC模型

| 角色 | 客户管理 | 合同管理 | 付款管理 | 智能问答 | 系统设置 |
|------|---------|---------|---------|---------|---------|
| **admin** | 全部 | 全部 | 全部 | 全部 | ✅ |
| **sales** | 仅自己的 | 仅自己的 | 仅自己的 | ✅ |  |
| **viewer** | 仅自己的(只读) | 仅自己的(只读) | 仅自己的(只读) | ✅ |  |
| **finance** | 全部(只读) | 全部(只读) | 全部 | ✅ | ❌ |

### 7.2 实现方式

```python
# backend/app/api/dependencies.py
from fastapi import Depends, HTTPException, status
from app.core.security import decode_access_token
from app.models.user import User
from app.db.session import SessionLocal

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """获取当前用户"""
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return user

def require_role(*allowed_roles: list[str]):
    """装饰器：要求特定角色"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user or current_user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 使用示例
@app.get("/contracts")
async def list_contracts(
    current_user: User = Depends(get_current_user),
    page: int = 1,
    per_page: int = 20
):
    query = db.query(Contract)
    
    # 非管理员只能查看自己负责的合同
    if current_user.role != UserRole.ADMIN:
        query = query.filter(Contract.sales_person_id == current_user.id)
    
    # ... 其他逻辑
```

---

## 8️⃣ 实施计划

### Phase 1：基础架构搭建（Week 1-2）

**目标：** 完成项目骨架，跑通Hello World

**任务清单：**
- [ ] 初始化FastAPI项目结构
- [ ] 配置PostgreSQL数据库 + Alembic迁移
- [ ] 实现用户认证（JWT登录/登出）
- [ ] 搭建React前端脚手架
- [ ] 编写单元测试框架

**交付物：**
- 可运行的空项目
- 登录/登出功能
- 数据库Schema V1

### Phase 2：客户与合同管理（Week 3-5）

**目标：** 实现核心CRUD功能

**任务清单：**
- [ ] 客户管理API（增删改查）
- [ ] 合同管理API（增删改查）
- [ ] 文件上传接口（本地存储）
- [ ] 前端客户列表/详情页
- [ ] 前端合同列表/详情页
- [ ] 合同上传功能（暂不解析）

**交付物：**
- 完整的客户/合同管理功能
- 文件上传下载功能
- 基础权限控制

### Phase 3：AI合同解析集成（Week 6-8）

**目标：** 实现合同自动解析

**任务清单：**
- [ ] 集成SiliconFlow Qwen-VL API
- [ ] 编写合同解析Prompt模板
- [ ] 实现异步解析任务（Celery）
- [ ] 解析结果展示与人工修正UI
- [ ] 解析准确率评估与优化
- [ ] 合同数据持久化

**交付物：**
- 合同上传→AI解析→人工确认完整流程
- 解析准确率≥85%

### Phase 4：付款跟踪功能（Week 9-11）

**目标：** 实现多期付款管理

**任务清单：**
- [ ] 付款计划创建API
- [ ] 付款凭证上传接口
- [ ] OCR识别付款凭证
- [ ] 自动计算剩余尾款
- [ ] 付款状态流转逻辑
- [ ] 前端付款看板

**交付物：**
- 完整的付款跟踪功能
- 尾款自动计算
- 付款凭证存档

### Phase 5：智能问答Agent（Week 12-14）

**目标：** 实现自然语言查询

**任务清单：**
- [ ] 意图识别模块
- [ ] SQL查询构建器
- [ ] LLM回答生成
- [ ] 对话历史管理
- [ ] 前端聊天界面
- [ ] 回答质量评估

**交付物：**
- 智能问答功能上线
- 支持常见业务查询

### Phase 6：优化与上线（Week 15-16）

**目标：** 生产环境部署

**任务清单：**
- [ ] 性能优化（数据库索引、缓存）
- [ ] 安全加固（HTTPS、CORS、限流）
- [ ] 监控告警（Prometheus + Grafana）
- [ ] 日志系统（ELK）
- [ ] 用户培训文档
- [ ] 生产环境部署

**交付物：**
- 生产环境稳定运行
- 完整文档体系

---

## 9️ 验收标准

### 功能验收
- [ ] 合同上传后AI自动解析，准确率≥85%
- [ ] 支持自定义多期付款，尾款自动计算准确
- [ ] 付款凭证图片存档，支持OCR搜索
- [ ] 智能问答能正确回答常见业务查询
- [ ] 业务员只能查看自己负责的客户数据

### 性能验收
- [ ] 合同列表加载 < 500ms（1000条数据）
- [ ] AI解析单个合同 < 30秒
- [ ] 支持并发上传10个文件

### 安全验收
- [ ] JWT认证 + RBAC权限控制
- [ ] 敏感字段加密存储
- [ ] 文件访问鉴权
- [ ] 完整审计日志

---

## 🔟 风险预案

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| AI解析准确率低 | 高 | 中 | 保留人工录入入口；持续优化Prompt；收集bad case改进模型 |
| 数据丢失 | 极高 | 低 | 每日数据库备份；文件哈希校验；异地容灾 |
| 性能瓶颈 | 中 | 中 | 数据库读写分离；Redis缓存热点数据；CDN加速文件下载 |
| 安全漏洞 | 极高 | 低 | 定期渗透测试；依赖漏洞扫描；最小权限原则 |
| API配额超限 | 中 | 中 | 监控API调用量；设置告警；准备备用模型供应商 |

---

## 📎 附录

### A. 真实合同样本字段映射

基于提供的《两地车牌指标过户服务合约》：

| 合同字段 | JSONB路径 | 示例值 |
|---------|-----------|--------|
| 甲方名称 | party_a.name | 华星智源开发有限公司 |
| 甲方联系 | party_a.contact | 98702065 |
| 乙方姓名 | party_b.name | 卢灿梅 |
| 证件类型 | party_b.id_type | 身份证 |
| 证件号码 | party_b.id_number | M60390A(7) |
| 车牌号 | service_content.license_plate | 粤ZS629港 |
| 通行口岸 | service_content.port | 莲塘口岸 |
| 总金额 | total_amount | 235000 |
| 定金 | payment_terms[0].amount | 20000 |
| 尾款 | payment_terms[1].amount | 215000 |

### B. 常见问题FAQ

**Q1: 为什么选择PostgreSQL而不是MySQL？**
A: PostgreSQL的JSONB字段更适合存储灵活的合同数据，GIN索引支持高效JSON查询，全文搜索能力更强。

**Q2: 为什么不直接用向量数据库？**
A: 一期以结构化查询为主，PostgreSQL的pgvector扩展已足够。二期如需语义搜索再引入专业向量库。

**Q3: 文件存储为何不用MinIO/OSS？**
A: 一期追求简单快速上线，本地文件系统足够。后期数据量大时再无缝切换到对象存储。

**Q4: AI解析失败怎么办？**
A: 系统提供人工录入/修正界面，保证业务流程不中断。同时记录失败案例用于模型优化。

**Q5: 如何保证AI回答不编造数据？**
A: 采用"先查数据库→再注入Prompt→LLM生成回答"的流程，严格限制LLM只能基于真实数据回答。

---

**文档结束**
