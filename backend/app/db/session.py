"""
数据库会话管理
"""
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import structlog
from app.config import settings

logger = structlog.get_logger()

# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 创建基类
class Base(DeclarativeBase):
    pass


def get_db():
    """获取数据库会话（用于依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error("database_query_error", error=str(e), exc_info=True)
        raise
    finally:
        db.close()
