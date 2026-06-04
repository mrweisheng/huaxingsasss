"""
Agent 相关的 Pydantic Schema
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AttachmentItem(BaseModel):
    file_id: str = Field(..., description="上传接口返回的文件ID")
    file_type: str = Field("image", description="文件类型: image/pdf/word/excel/text")


class ChatRequest(BaseModel):
    question: str = Field(default="", max_length=5000, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID，为空则创建新会话")
    attachments: Optional[List[AttachmentItem]] = Field(None, description="附件列表")


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    tokens_used: int = 0


class SessionResponse(BaseModel):
    session_id: str
    created_at: datetime
    message_count: int = 0
    title: Optional[str] = None
    mode: str = "chat"
    context: Optional[dict] = None


class UploadResponse(BaseModel):
    file_id: str
    file_name: str
    file_size: int


class CreateSessionRequest(BaseModel):
    """创建会话请求 — 支持指定 mode 和 context"""
    title: Optional[str] = None
    mode: str = Field(default="chat", description="会话模式: chat | receipt_income | receipt_expense")
    context: Optional[dict] = Field(None, description="模式上下文，如 {contract_id, payment_type}")
