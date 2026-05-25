"""
数据库模型基类
"""
from sqlalchemy import Column, Integer, DateTime, DECIMAL
from sqlalchemy.sql import func
from app.db.session import Base


class BaseModel(Base):
    """模型基类，包含通用字段"""
    
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
