"""
ChatSession 会话元数据模型
存储 session 级别的 mode、context 等信息，
与 chat_history 通过 session_id 关联。
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel


class ChatSession(BaseModel):
    """会话元数据"""

    __tablename__ = "chat_sessions"

    session_id = Column(String(36), unique=True, nullable=False, index=True, comment="会话UUID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    title = Column(String(200), nullable=True, comment="会话标题")
    mode = Column(
        String(20),
        nullable=False,
        default="chat",
        server_default="chat",
        comment="会话模式: chat | receipt_income | receipt_expense",
    )
    context = Column(JSONB, nullable=True, comment="模式上下文，如 {contract_id, payment_type}")
