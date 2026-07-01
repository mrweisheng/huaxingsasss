"""
Agent 相关的 Pydantic Schema
"""
import os
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


# 后缀 → file_type 映射（不识别时设为空字符串，由 analyze_files 自行判断）
_EXT_TO_FILE_TYPE = {
    ".pdf": "pdf",
    ".doc": "word", ".docx": "word",
    ".xls": "excel", ".xlsx": "excel",
    ".txt": "text", ".csv": "text",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".gif": "image", ".bmp": "image", ".webp": "image",
    ".heic": "image", ".heif": "image",
}


class AttachmentItem(BaseModel):
    file_id: str = Field(..., description="上传接口返回的文件ID")
    file_type: str = Field("", description="文件类型: image/pdf/word/excel/text（空=未知，由 analyze_files 判断）")
    file_name: Optional[str] = Field(None, description="原始文件名（用于 LLM 判断文件用途）")

    @model_validator(mode="after")
    def infer_file_type_from_name(self) -> "AttachmentItem":
        """如果 file_type 为空或仍为默认的 'image'，尝试从 file_name 后缀推断。"""
        if self.file_name and (not self.file_type or self.file_type == "image"):
            ext = os.path.splitext(self.file_name)[1].lower()
            if ext in _EXT_TO_FILE_TYPE:
                self.file_type = _EXT_TO_FILE_TYPE[ext]
        return self


class ChatRequest(BaseModel):
    question: str = Field(default="", max_length=5000, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID，为空则创建新会话")
    attachments: Optional[List[AttachmentItem]] = Field(None, description="附件列表")


class CreateSessionRequest(BaseModel):
    """创建会话请求 — 支持指定 mode 和 context"""
    title: Optional[str] = None
    mode: str = Field(default="chat", description="会话模式: chat | receipt_income | receipt_expense")
    context: Optional[dict] = Field(None, description="模式上下文，如 {contract_id, payment_type}")
