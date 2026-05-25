"""
智能问答API路由 - TODO: Phase 5实现
"""
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.response import ResponseModel

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求体"""
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    session_id: Optional[str] = Field(None, description="会话ID")


@router.post("/chat")
def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """智能问答 - TODO: Phase 5实现完整的意图识别+SQL构建+LLM回答"""
    return ResponseModel(
        code=200,
        message="TODO: 实现智能问答",
        data={
            "answer": f"您问的问题是：{request.question}（智能问答功能将在 Phase 5 实现）",
            "session_id": request.session_id or "new-session"
        }
    )


@router.get("/history")
def get_chat_history(
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取对话历史 - TODO"""
    return ResponseModel(
        code=200,
        message="TODO: 获取对话历史",
        data=[]
    )
