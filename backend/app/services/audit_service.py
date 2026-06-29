"""
审计日志服务

记录所有业务操作到 audit_logs 表
"""
import json
from datetime import date, datetime
from decimal import Decimal
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
            old_values=AuditService._json_safe(old_values or {}),
            new_values=AuditService._json_safe(new_values or {}),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(log_entry)
        db.commit()
        return log_entry

    @staticmethod
    def _json_safe(values: dict) -> dict:
        """把 values 转成 JSON 可序列化结构。

        audit_logs.old_values / new_values 落库到 JSON 列，遇到 date / datetime /
        Decimal / set 等类型会抛 TypeError，导致整个请求 500（旧 bug：编辑带
        date 字段的实体时序列化失败引发 PendingRollbackError）。
        此处统一兜底，保证审计日志写入不阻断业务流程。
        """
        def convert(v: Any) -> Any:
            if isinstance(v, Decimal):
                return float(v)
            if isinstance(v, (date, datetime)):
                return v.isoformat()
            if isinstance(v, dict):
                return {k: convert(val) for k, val in v.items()}
            if isinstance(v, (list, tuple)):
                return [convert(x) for x in v]
            return v
        try:
            # 先转换已知类型，再用 json.dumps/doubledecode 兜底剥离任何残留不可序列化对象
            safe = {k: convert(v) for k, v in values.items()}
            return json.loads(json.dumps(safe, default=str, ensure_ascii=False))
        except Exception:
            # 极端情况：降级为字符串，绝不阻断业务
            return {str(k): str(v) for k, v in values.items()}

