"""
智能问答 API 路由 — Agent SSE 流式对话
"""
import json
import os
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.agent import ChatRequest, UploadResponse
from app.ai.agent import ContractAgent
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/sessions")
def create_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建新会话"""
    session_id = str(uuid.uuid4())
    return {
        "code": 200,
        "data": {
            "session_id": session_id,
            "created_at": None,
            "message_count": 0,
        },
    }


@router.get("/sessions")
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户的所有会话"""
    agent = ContractAgent(db, current_user)
    sessions = agent.get_sessions()
    return {"code": 200, "data": sessions}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除会话"""
    agent = ContractAgent(db, current_user)
    deleted = agent.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"code": 200, "data": None}


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SSE 流式对话"""
    question = request.question or ""
    if not question.strip() and request.attachments:
        # 根据附件类型动态生成默认提示词
        has_pdf = any(a.file_type == "pdf" for a in request.attachments)
        has_image = any(a.file_type in ("image", "receipt") for a in request.attachments)
        if has_pdf and has_image:
            question = "请分析上传的文件（含 PDF 和图片）"
        elif has_pdf:
            question = "请分析上传的 PDF 文件内容"
        else:
            question = "请分析上传的图片内容"

    agent = ContractAgent(db, current_user)

    async def event_generator():
        try:
            async for event in agent.chat(
                session_id=request.session_id,
                user_message=question,
                attachments=[a.model_dump() for a in request.attachments] if request.attachments else None,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Agent chat error")
            error_event = {
                "event": "error",
                "data": {"message": f"对话出错: {str(e)}"},
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传文件到临时目录，供聊天中使用"""
    os.makedirs(settings.TEMP_UPLOAD_DIR, exist_ok=True)

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件过大")

    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.TEMP_UPLOAD_DIR, file_id)

    with open(file_path, "wb") as f:
        f.write(content)

    return {
        "code": 200,
        "data": {
            "file_id": file_id,
            "file_name": file.filename,
            "file_size": len(content),
        },
    }


@router.get("/history/{session_id}")
def get_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取会话消息历史"""
    agent = ContractAgent(db, current_user)
    history = agent.get_history(session_id)
    return {"code": 200, "data": history}
