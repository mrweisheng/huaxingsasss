"""
数据库模型基类
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, DateTime, Boolean, func
from app.db.session import Base


class BaseModel(Base):
    """模型基类，包含通用字段"""

    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    is_deleted = Column(Boolean, default=False, server_default="false", comment="软删除标记")
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment="软删除时间")

    def soft_delete(self):
        """软删除"""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
