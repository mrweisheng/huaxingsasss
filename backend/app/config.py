"""
应用配置管理模块
从环境变量读取配置，提供类型安全的配置访问
"""
from typing import Optional
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator


class Settings(BaseSettings):
    """应用配置类"""

    # 应用基础配置
    APP_NAME: str = "合同管理系统"
    APP_ENV: str = "development"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 数据库配置（全部必填，漏配直接报错，不留默认值兜底）
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    @property
    def DATABASE_URL(self) -> str:
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql://{self.POSTGRES_USER}:{password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            password = quote_plus(self.REDIS_PASSWORD)
            return f"redis://:{password}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # AI服务配置（DeepSeek 官方 - Agent 推理 + 文本结构化）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_AGENT_MODEL: str = "deepseek-v4-flash"

    # AI服务配置（阿里云百炼 - 视觉模型）
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_VISION_MODEL: str = "qwen3-vl-flash"

    # Agent 重试配置
    AGENT_MAX_RETRIES: int = 3
    AGENT_RETRY_BASE_DELAY: float = 1.0

    # LangSmith 可观测性（Phase 2.7）
    # 设为 true 后 LangChain/LangGraph 自动追踪到 LangSmith UI
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "huaxing-agent"

    # Agent配置
    AGENT_MAX_ITERATIONS: int = 8

    # 业务开关：收入是否强制关联凭证
    # False（默认，现阶段）：收入凭证可选，无凭证可直接录入并结算，notes 打 [无凭证收入] 标记
    # True（将来恢复）：收入必须上传凭证，无凭证在各层（schema/api/service/工具/prompt）被拦截
    INCOME_RECEIPT_REQUIRED: bool = False

    # 文件存储配置
    UPLOAD_DIR: str = "/data/contract-system"
    CONTRACT_UPLOAD_DIR: str = "/data/contract-system/contracts"
    RECEIPT_UPLOAD_DIR: str = "/data/contract-system/receipts"
    SCREENSHOT_UPLOAD_DIR: str = "/data/contract-system/screenshots"
    TEMP_UPLOAD_DIR: str = "/data/contract-system/temp"
    AGENT_FILE_DIR: str = "/data/contract-system/agent-files"  # Agent 持久化附件（历史回看）
    MAX_FILE_SIZE: int = 52428800  # 50MB

    # 日志配置
    LOG_LEVEL: str = "DEBUG"

    @model_validator(mode="after")
    def validate_required(self):
        """启动时校验必填配置项——缺失或为空直接拒绝启动，不留任何兜底默认值。"""
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY 必须设置且长度 ≥ 32 字符。"
                "请检查 .env 文件或环境变量。"
            )
        # 数据库连接信息：任一缺失/为空即拒绝启动
        db_fields = {
            "POSTGRES_SERVER": self.POSTGRES_SERVER,
            "POSTGRES_DB": self.POSTGRES_DB,
            "POSTGRES_USER": self.POSTGRES_USER,
            "POSTGRES_PASSWORD": self.POSTGRES_PASSWORD,
        }
        missing = [k for k, v in db_fields.items() if not v or not str(v).strip()]
        if missing:
            raise ValueError(
                f"数据库配置缺失：{', '.join(missing)}。"
                "请检查 .env 文件或环境变量，禁止使用硬编码默认值。"
            )
        if not self.DEEPSEEK_API_KEY:
            raise ValueError(
                "DEEPSEEK_API_KEY 必须设置。"
                "请检查 .env 文件或环境变量。"
            )
        if not self.DASHSCOPE_API_KEY:
            raise ValueError(
                "DASHSCOPE_API_KEY 必须设置。"
                "请检查 .env 文件或环境变量。"
            )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # 容忍 .env 中的多余键（如已废弃但未清理的配置项），避免删除字段定义后启动崩溃
        extra = "ignore"


# 创建全局配置实例
settings = Settings()
