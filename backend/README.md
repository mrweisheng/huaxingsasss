# 合同管理系统 - 后端

企业级合同管理与智能客服系统后端服务

## 快速开始

### 1. 安装依赖

```bash
cd backend
poetry install
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑.env文件，修改数据库连接、AI API密钥等配置
```

### 3. 启动数据库（Docker）

```bash
docker-compose up -d postgres redis
```

### 4. 运行数据库迁移

```bash
cd migrations
alembic upgrade head
```

### 5. 启动开发服务器

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看API文档

## 项目结构

```
backend/
├── app/
│   ├── api/v1/          # API路由
│   │   ├── auth.py      # 认证接口 ✅
│   │   ├── customers.py # 客户接口 ✅
│   │   ├── contracts.py # 合同接口 ⏳
│   │   ├── payments.py  # 付款接口 ⏳
│   │   ├── agent.py     # 智能问答 ⏳
│   │   └── files.py     # 文件管理 ⏳
│   ├── models/          # SQLAlchemy模型 ✅
│   ├── schemas/         # Pydantic模型 ✅
│   ├── services/        # 业务逻辑层 ⏳
│   ├── ai/              # AI集成 ⏳
│   ├── core/            # 核心模块 ✅
│   ├── db/              # 数据库会话 ✅
│   └── utils/           # 工具函数 ✅
├── migrations/          # Alembic迁移 ✅
├── tests/               # 测试 ⏳
── docker-compose.yml   # Docker编排 ✅
├── Dockerfile           # Docker镜像 ✅
├── pyproject.toml       # 依赖管理 ✅
└── README.md            # 本文档
```

## 已完成功能

- ✅ 用户认证（JWT登录/登出/刷新）
- ✅ 客户管理CRUD
- ✅ 数据库表结构（7张表）
- ✅ 多币种支持（CNY/HKD/USD）
- ✅ 汇率管理表
- ✅ Docker开发环境

## 待实现功能

- ⏳ 合同管理（上传、AI解析、CRUD）
- ⏳ 付款跟踪（多期付款、凭证上传、汇率结算）
- ⏳ 汇率服务（查询、录入、自动折算）
- ⏳ 智能问答（意图识别、SQL生成、自然语言回答）
- ⏳ 文件管理（上传、下载、OCR索引）
- ⏳ AI集成（SiliconFlow Qwen-VL）

## API文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 默认账户

- 用户名: admin
- 密码: admin123456
- 角色: admin（管理员）

## 技术栈

- Python 3.11+
- FastAPI 0.109+
- PostgreSQL 15+
- Redis 7+
- SQLAlchemy 2.0+
- Pydantic 2.5+

## 开发规范

1. 所有API返回统一格式：`ResponseModel`
2. 使用Pydantic进行数据验证
3. 使用Alembic管理数据库迁移
4. 编写单元测试覆盖核心逻辑
5. 遵循PEP 8代码规范
