"""
Agent 相关的 Pydantic Schema
"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, model_validator


class AttachmentItem(BaseModel):
    file_id: str = Field(..., description="上传接口返回的文件ID")
    file_type: str = Field("image", description="文件类型: image/pdf/word/excel/text")


class ChatRequest(BaseModel):
    question: str = Field(default="", max_length=5000, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID，为空则创建新会话")
    attachments: Optional[List[AttachmentItem]] = Field(None, description="附件列表")

    # Phase 1 新增：中断恢复（ADR #1）
    resume: Optional[dict] = Field(
        default=None,
        description="Command(resume=) 载荷，例如 {'confirmed': True}。与 question/attachments 互斥。",
    )
    interrupt_id: Optional[str] = Field(
        default=None,
        description="待恢复的 interrupt_id，与 checkpoint 中待处理中断匹配才能 resume",
    )

    @model_validator(mode="after")
    def check_resume_consistency(self) -> "ChatRequest":
        """resume 与 question/attachments 互斥"""
        if self.resume is not None:
            if self.question or self.attachments:
                raise ValueError("resume 非空时，question 和 attachments 必须为空")
        return self


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
