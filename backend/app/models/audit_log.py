"""
审计日志模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, INET, Index
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import BaseModel


class AuditLog(BaseModel):
    """操作日志表"""
    
    __tablename__ = "audit_logs"
    
    user_id = Column(Integer, ForeignKey("users.id"), index=True, comment="用户ID")
    action = Column(String(50), nullable=False, index=True, comment="操作类型")
    entity_type = Column(String(50), nullable=False, index=True, comment="实体类型")
    entity_id = Column(Integer, index=True, comment="实体ID")
    old_values = Column(JSONB, comment="修改前的值")
    new_values = Column(JSONB, comment="修改后的值")
    ip_address = Column(INET, comment="IP地址")
    user_agent = Column(Text, comment="User-Agent")
    
    # 索引
    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_created", "created_at"),
        Index("idx_audit_action", "action"),
    )
