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
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 数据库配置
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "contract_db"
    POSTGRES_USER: str = "admin"
    POSTGRES_PASSWORD: str = "dev_password"
    
    @property
    def DATABASE_URL(self) -> str:
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql://{self.POSTGRES_USER}:{password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
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
    
    # Celery配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # AI服务配置（SiliconFlow - Agent 推理模型）
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_VISION_MODEL: str = "Qwen/Qwen3-VL-32B-Instruct"
    SILICONFLOW_TEXT_MODEL: str = "Qwen/Qwen3-VL-8B-Instruct"
    SILICONFLOW_AGENT_MODEL: str = "deepseek-ai/DeepSeek-V4-Flash"

    # AI服务配置（阿里云百炼 - 视觉模型）
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_VISION_MODEL: str = "qwen3-vl-flash"
    DASHSCOPE_TEXT_MODEL: str = "qwen-plus"  # 文本模型，用于合同结构化提取

    # Agent 重试配置
    AGENT_MAX_RETRIES: int = 3

    # LangSmith 可观测性（Phase 2.7）
    # 设为 true 后 LangChain/LangGraph 自动追踪到 LangSmith UI
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "huaxing-agent"
    AGENT_RETRY_BASE_DELAY: float = 1.0

    # Agent配置
    AGENT_MAX_ITERATIONS: int = 8
    AGENT_HISTORY_WINDOW: int = 100  # 历史加载上限（条数）
    AGENT_MAX_SUMMARY_MESSAGES: int = 10  # 摘要后保留的最近消息条数
    
    # 文件存储配置
    UPLOAD_DIR: str = "/data/contract-system"
    CONTRACT_UPLOAD_DIR: str = "/data/contract-system/contracts"
    RECEIPT_UPLOAD_DIR: str = "/data/contract-system/receipts"
    SCREENSHOT_UPLOAD_DIR: str = "/data/contract-system/screenshots"
    TEMP_UPLOAD_DIR: str = "/data/contract-system/temp"
    MAX_FILE_SIZE: int = 52428800  # 50MB
    
    # 日志配置
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "json"
    
    # 汇率配置（项目仅支持 CNY 和 HKD，故只需 HKD/CNY 默认值）
    DEFAULT_EXCHANGE_RATE_HKD_CNY: float = 0.92
    
    @model_validator(mode="after")
    def validate_required(self):
        """启动时校验必填配置项"""
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY 必须设置且长度 ≥ 32 字符。"
                "请检查 .env 文件或环境变量。"
            )
        if not self.SILICONFLOW_API_KEY:
            raise ValueError(
                "SILICONFLOW_API_KEY 必须设置。"
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


# 创建全局配置实例
settings = Settings()
