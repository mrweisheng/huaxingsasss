"""
审计日志服务

记录所有业务操作到 audit_logs 表
"""
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


class AuditService:
    """审计日志服务"""

    @staticmethod
    def log(
        db: Session,
        user_id: int,
        action: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """
        记录审计日志

        Args:
            db: 数据库会话
            user_id: 操作用户ID
            action: 操作类型 (create/update/delete/upload/login)
            entity_type: 实体类型 (customer/contract/payment/file/user)
            entity_id: 实体ID
            old_values: 修改前的值
            new_values: 修改后的值
            ip_address: 客户端IP
            user_agent: 客户端 User-Agent

        Returns:
            创建的审计日志记录
        """
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values or {},
            new_values=new_values or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(log_entry)
        db.commit()
        return log_entry
