"""
智能问答 API 路由 — Agent SSE 流式对话
"""
import json
import os
import uuid
import logging
import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.core.permissions import is_admin
from app.models.user import User
from app.models.chat_session import ChatSession
from app.models.agent_file import AgentFile
from app.schemas.agent import ChatRequest, UploadResponse, CreateSessionRequest
from app.ai.chat_session_service import ContractAgent
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/sessions")
def create_session(
    req: CreateSessionRequest = CreateSessionRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建新会话，支持指定 mode（chat/receipt_income/receipt_expense）和 context"""
    session_id = str(uuid.uuid4())

    # 持久化会话元数据
    chat_session = ChatSession(
        session_id=session_id,
        user_id=current_user.id,
        title=req.title,
        mode=req.mode,
        context=req.context,
    )
    db.add(chat_session)
    db.commit()

    return {
        "code": 200,
        "data": {
            "session_id": session_id,
            "created_at": chat_session.created_at.isoformat() if chat_session.created_at else None,
            "message_count": 0,
            "title": req.title,
            "mode": req.mode,
            "context": req.context,
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
    http_request: Request,
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SSE 流式对话"""
    # ===== 调试日志 =====
    logger.info("=" * 60)
    logger.info("[AGENT CHAT] 收到聊天请求")
    logger.info("[AGENT CHAT] user: %s", current_user.username)
    logger.info("[AGENT CHAT] session_id: %s", request.session_id)
    logger.info("[AGENT CHAT] question: %s", request.question or "(空)")
    logger.info("[AGENT CHAT] attachments: %s", request.attachments)
    if request.attachments:
        for i, att in enumerate(request.attachments):
            logger.info("[AGENT CHAT]   attachment[%d]: file_id=%s, file_type=%s", i, att.file_id, att.file_type)
    else:
        logger.info("[AGENT CHAT]   attachments: None (请求中没有 attachments 字段)")
    logger.info("=" * 60)
    # ====================

    question = request.question or ""
    auto_filled = False
    if not question.strip() and request.attachments:
        # 根据附件类型动态生成默认提示词，标记为自动补全（用于 chat_history 元数据）
        auto_filled = True
        types = {a.file_type for a in request.attachments}
        type_labels = []
        if "image" in types or "receipt" in types:
            type_labels.append("图片")
        if "pdf" in types:
            type_labels.append("PDF")
        if "word" in types:
            type_labels.append("Word 文档")
        if "excel" in types:
            type_labels.append("Excel 表格")
        if "text" in types:
            type_labels.append("文本文件")

        if len(type_labels) > 1:
            joined = "、".join(type_labels)
            question = f"请分析上传的文件（包含{joined}），提取关键信息并总结内容"
        elif len(type_labels) == 1:
            question = f"请分析上传的{type_labels[0]}内容，提取关键信息并总结"
        else:
            question = "请分析上传的文件内容"

    # 注意：POST /chat 主链路不消费 mode。session.mode 字段记录能力卡片意图供 LLM 上下文参考，
    # 实际意图推断由 LLM 通过 analyze_files 工具自主决定。

    async def event_generator():
        try:
            # ━━━ v2 统一 Agent 图（单层循环，进程级缓存） ━━━
            from app.ai.orchestrator.unified_agent import get_compiled_graph, _default_llm_client
            from app.ai.tool_executor import ToolExecutorV2
            from app.ai.orchestrator.sse_adapter import adapt_langgraph_stream_v2
            from app.ai.orchestrator.checkpointer import get_checkpointer

            try:
                cp = get_checkpointer()
            except RuntimeError as e:
                logger.error("checkpointer 未初始化: %s", e)
                raise HTTPException(
                    status_code=503,
                    detail="LangGraph checkpointer 未初始化，请联系管理员",
                )

            session_id = request.session_id or str(uuid.uuid4())

            # ━━━ 加载 session 上下文（mode + context），注入 initial_state 供 LLM 感知 ━━━
            session_context = None
            session_mode = "chat"
            if request.session_id:
                session_record = (
                    db.query(ChatSession)
                    .filter(ChatSession.session_id == request.session_id)
                    .first()
                )
                if session_record:
                    session_mode = session_record.mode or "chat"
                    session_context = session_record.context or None
                    logger.info(
                        "[AGENT CHAT] 加载 session 上下文: mode=%s context=%s",
                        session_mode, session_context,
                    )

            # 请求级依赖注入（db/user/executor/llm_client 不参与 checkpoint）
            deps = {
                "db": db,
                "user": current_user,
                "executor": ToolExecutorV2(db, current_user),
                "llm_client": _default_llm_client(),
            }
            config = {
                "configurable": {
                    "thread_id": session_id,
                    "_deps": deps,
                },
            }

            # 获取缓存的编译图（按 checkpointer 实例区分）
            compiled_app = get_compiled_graph(checkpointer=cp)

            # 构造 initial_state
            from langchain_core.messages import HumanMessage
            human_kwargs = {}
            if auto_filled:
                human_kwargs["auto_filled"] = True
            if request.attachments:
                # 把附件元信息直接挂到 HumanMessage，方便 finalize_node 落库
                human_kwargs["attachments"] = [a.model_dump() for a in request.attachments]
            initial_state = {
                "messages": [HumanMessage(
                    content=question,
                    additional_kwargs=human_kwargs,
                )],
                "user_id": current_user.id,
                "user_role": current_user.role,
                "session_id": session_id,
                "session_context": session_context,
                "session_mode": session_mode,
                "_finalized": False,
                "should_end": False,
                "iteration_count": 0,
            }
            if request.attachments:
                initial_state["attachments"] = [a.model_dump() for a in request.attachments]
            else:
                initial_state["attachments"] = []

            async for sse_line in adapt_langgraph_stream_v2(
                compiled_app.astream_events(
                    initial_state, config, version="v2",
                ),
                session_id,
            ):
                if http_request and await http_request.is_disconnected():
                    return
                yield sse_line
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
    db: Session = Depends(get_db),
):
    """上传文件到持久化目录 + 落 agent_file 表，供聊天 + 历史回看共用。

    路径格式：AGENT_FILE_DIR/{user_id}/{file_id}{ext}
    - 与之前的 TEMP_UPLOAD_DIR 相同的平铺结构，resolve_file_path 兼容查找
    - 上传时 session_id 留空，finalize_node 落库时按 file_id 回填
    - 历史回看通过 GET /agent/files/{file_id} 拉取
    """
    user_dir = os.path.join(settings.AGENT_FILE_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件过大")

    file_id = str(uuid.uuid4())
    # 保留原始文件扩展名，避免后续 guess_extension 无法识别 Word/Excel 等格式
    original_ext = ""
    if file.filename and "." in file.filename:
        original_ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    fname_on_disk = file_id + original_ext
    file_path = os.path.join(user_dir, fname_on_disk)

    with open(file_path, "wb") as f:
        f.write(content)

    original_name = file.filename

    # HEIC/HEIF 入站立即转码为 JPEG：浏览器（Windows Chrome）不能可靠解码 HEIC，
    # 下游 VL/压缩管线统一吃 JPEG/PNG。转码后覆盖原文件，简化生命周期与历史回看。
    if original_ext in (".heic", ".heif"):
        try:
            from PIL import Image
            import io as _io
            # 端点级兜底注册：即使 startup 钩子未跑或被绕过，也保证 PIL 能识别 HEIC。
            # register_heif_opener 是幂等操作，重复调用安全；缺包/缺底层 libheif 时
            # 走 except 链路给前端 400 友好提示。
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
            except Exception as reg_exc:
                logger.warning("pillow_heif 注册失败: %s", reg_exc)
            with Image.open(_io.BytesIO(content)) as img:
                rgb = img.convert("RGB")
                buf = _io.BytesIO()
                rgb.save(buf, format="JPEG", quality=85)
                jpeg_bytes = buf.getvalue()
        except Exception as exc:
            # 解码失败：删除已落盘的脏文件，告诉用户重传
            try:
                os.remove(file_path)
            except OSError:
                pass
            logger.warning("HEIC 解码失败: %s, file=%s", exc, file.filename)
            raise HTTPException(
                status_code=400,
                detail="HEIC 文件解码失败，请重新拍摄或转为 JPG 后再上传",
            )

        # 用 JPEG 覆盖
        original_ext = ".jpg"
        fname_on_disk = file_id + original_ext
        new_file_path = os.path.join(user_dir, fname_on_disk)
        with open(new_file_path, "wb") as f:
            f.write(jpeg_bytes)
        if new_file_path != file_path:
            try:
                os.remove(file_path)
            except OSError:
                pass
        file_path = new_file_path
        content = jpeg_bytes
        # 文件名也同步改后缀，避免历史回看下载到无法预览的 .heic
        if original_name:
            base = original_name.rsplit(".", 1)[0]
            original_name = f"{base}.jpg"

    # 为图片文件生成缩略图（200px），供前端在 HEIC 等浏览器不支持的格式上传后展示预览。
    # 直接返回 data URL：浏览器原生 <img src> 不会带 Authorization 头，走 API 路径必 401；
    # 200px JPEG 体积约 15-25KB，base64 后 ~30KB，单次上传响应可接受。
    thumbnail_url = None
    _image_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif")
    if original_ext in _image_exts:
        try:
            import base64 as _b64
            from PIL import Image as PILImage
            import io as _io2
            with PILImage.open(_io2.BytesIO(content)) as img:
                img.thumbnail((200, 200), PILImage.LANCZOS)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                thumb_buf = _io2.BytesIO()
                img.save(thumb_buf, format="JPEG", quality=80)
                thumb_bytes = thumb_buf.getvalue()
            # 物理文件留存，兼容旧的 /thumbnail 端点和将来可能的服务端使用
            thumb_name = f"{file_id}_thumb.jpg"
            thumb_path = os.path.join(user_dir, thumb_name)
            with open(thumb_path, "wb") as f:
                f.write(thumb_bytes)
            thumbnail_url = "data:image/jpeg;base64," + _b64.b64encode(thumb_bytes).decode("ascii")
        except Exception:
            # 缩略图生成失败不影响主流程
            pass

    # 推断 file_type 分类（与前端 FileType 对齐）
    ext = original_ext.lstrip(".")
    if ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp"):
        file_type = "image"
    elif ext == "pdf":
        file_type = "pdf"
    elif ext in ("doc", "docx"):
        file_type = "word"
    elif ext in ("xls", "xlsx"):
        file_type = "excel"
    elif ext in ("txt", "csv", "md"):
        file_type = "text"
    else:
        file_type = "text"

    mime_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    # HEIC 已转 JPEG，mime 同步覆盖（前端 content_type 可能仍是 image/heic）
    if ext in ("jpg", "jpeg"):
        mime_type = "image/jpeg"

    # PDF 计算页数 —— 前端文件卡片要展示"共 N 页"，让用户对识别耗时有预期
    # 仅 PDF 算（其他类型恒为 None），不入库，仅 response 透传
    page_count: Optional[int] = None
    if file_type == "pdf":
        try:
            import fitz
            with fitz.open(stream=content, filetype="pdf") as _doc:
                page_count = _doc.page_count
        except Exception:
            page_count = None  # 损坏的 PDF 容错，不阻断上传

    # 落表（相对路径只存 user_id/filename，避免绝对路径硬编码）
    relative_path = f"{current_user.id}/{fname_on_disk}"
    record = AgentFile(
        file_id=file_id,
        user_id=current_user.id,
        session_id=None,  # finalize_node 回填
        original_name=original_name,
        mime_type=mime_type,
        file_size=len(content),
        storage_path=relative_path,
        file_type=file_type,
    )
    db.add(record)
    db.commit()

    return {
        "code": 200,
        "data": {
            "file_id": file_id,
            "file_name": file.filename,
            "file_size": len(content),
            "thumbnail_url": thumbnail_url,
            "page_count": page_count,
        },
    }


@router.get("/files/{file_id}")
def get_agent_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按 file_id 拉取附件物理文件（鉴权 + 文件 owner 校验）。

    用于历史会话回看时前端从接口拿原文件渲染（图片走 Blob URL，文档触发下载）。
    旧会话（agent_file 表里没记录）→ 404。
    文件已被清理 → 410 Gone（明确语义，让前端展示「附件已失效」）。
    """
    record = (
        db.query(AgentFile)
        .filter(AgentFile.file_id == file_id, AgentFile.is_deleted == False)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="附件不存在或已失效")

    if record.user_id != current_user.id and not is_admin(current_user):
        raise HTTPException(status_code=403, detail="无权访问该附件")

    full_path = Path(settings.AGENT_FILE_DIR) / record.storage_path
    if not full_path.exists():
        raise HTTPException(status_code=410, detail="附件已被清理")

    return FileResponse(
        path=str(full_path),
        media_type=record.mime_type or "application/octet-stream",
        filename=record.original_name or file_id,
    )


@router.get("/files/{file_id}/thumbnail")
def get_agent_file_thumbnail(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按 file_id 拉取附件缩略图（JPEG 格式）。

    用于前端在 HEIC 等浏览器不支持的格式上传后展示预览。
    """
    record = (
        db.query(AgentFile)
        .filter(AgentFile.file_id == file_id, AgentFile.is_deleted == False)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="附件不存在或已失效")

    if record.user_id != current_user.id and not is_admin(current_user):
        raise HTTPException(status_code=403, detail="无权访问该附件")

    thumb_name = f"{file_id}_thumb.jpg"
    thumb_path = Path(settings.AGENT_FILE_DIR) / str(record.user_id) / thumb_name
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="缩略图不存在")

    return FileResponse(
        path=str(thumb_path),
        media_type="image/jpeg",
    )


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
