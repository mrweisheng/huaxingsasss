"""
智能问答 API 路由 — Agent SSE 流式对话
"""
import json
import os
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.chat_session import ChatSession
from app.schemas.agent import ChatRequest, UploadResponse, CreateSessionRequest
from app.ai.agent import ContractAgent
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
            "created_at": None,
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
    if not question.strip() and request.attachments:
        # 根据附件类型动态生成默认提示词
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

    agent = ContractAgent(db, current_user)

    async def event_generator():
        try:
            # ━━━ Phase 1：中断恢复 + 合同录入 LangGraph 路径 ━━━
            from app.ai.orchestrator.graph import build_root_graph
            from app.ai.orchestrator.contract_entry import ContractEntrySubgraph
            from app.ai.orchestrator.sse_adapter import adapt_langgraph_stream
            from app.ai.orchestrator.checkpointer import get_checkpointer

            # 检测是否应走 LangGraph 路径
            use_langgraph = False

            if request.resume:
                # 中断恢复：校验 interrupt_id（Phase 1 基础校验，完整 checkpoint 校验待 Phase 2）
                if not request.interrupt_id or not isinstance(request.interrupt_id, str):
                    yield f"data: {json.dumps({'event': 'error', 'data': {'message': '中断恢复缺少有效的 interrupt_id'}}, ensure_ascii=False)}\n\n"
                    return
                # 中断恢复：走 LangGraph
                use_langgraph = True
            elif request.attachments and any(
                a.file_type in ("pdf", "word", "excel") for a in request.attachments
            ):
                # 文档附件 → 合同录入子图
                use_langgraph = True

            if use_langgraph:
                try:
                    cp = get_checkpointer()
                except RuntimeError as e:
                    # checkpointer 缺失是部署故障，抛 503 比静默降级更安全
                    logger.error("checkpointer 未初始化: %s", e)
                    raise HTTPException(
                        status_code=503,
                        detail="LangGraph checkpointer 未初始化，请联系管理员",
                    )

                # 加载 session 元数据（mode / session_context 用于 ToolExecutor 守卫）
                agent._load_session_meta(request.session_id)

                config = {
                    "configurable": {"thread_id": request.session_id or str(uuid.uuid4())},
                }
                session_id = config["configurable"]["thread_id"]

                # ━━━ 中断恢复：校验 interrupt_id 与 checkpoint 匹配 ━━━
                if request.resume:
                    try:
                        state_snapshot = await cp.aget(config)
                        pending_ids = [
                            i.id for i in (state_snapshot.interrupts or [])
                        ]
                        if request.interrupt_id not in pending_ids:
                            logger.warning(
                                "interrupt_id 不匹配: received=%s pending=%s thread=%s",
                                request.interrupt_id, pending_ids, session_id,
                            )
                            yield f"data: {json.dumps({'event': 'error', 'data': {'message': 'interrupt_id 不匹配当前待处理中断'}}, ensure_ascii=False)}\n\n"
                            return
                    except Exception as e:
                        logger.error("checkpoint 查询失败: %s", e)
                        yield f"data: {json.dumps({'event': 'error', 'data': {'message': '无法验证中断状态，请稍后重试'}}, ensure_ascii=False)}\n\n"
                        return

                # 构建子图 + 根图。mode / session_context 通过构造函数注入到子图闭包
                # 内的 ToolExecutor，而不是修改 agent.executor（那是另一个实例）。
                # agent 注入 finalize_node 用于 chat_history 落库（ADR #6）。
                contract_entry = ContractEntrySubgraph(
                    db, current_user, agent,
                    mode=agent._mode,
                    session_context=agent._session_context,
                    session_id=session_id,
                )
                contract_app = contract_entry.build(checkpointer=cp)
                root_app = build_root_graph(contract_app, checkpointer=cp, agent=agent)

                # 构造 initial_state
                from langchain_core.messages import HumanMessage
                initial_state = {
                    "messages": [HumanMessage(content=question)],
                    "user_id": current_user.id,
                    "user_role": current_user.role,
                    "session_id": session_id,
                    "attachments": [a.model_dump() for a in request.attachments] if request.attachments else [],
                    "executor_mode": agent._mode,
                    "session_context": agent._session_context or {},
                }

                if request.resume:
                    # 中断恢复（校验已在上方完成）
                    from langgraph.types import Command
                    async for sse_line in adapt_langgraph_stream(
                        root_app.astream_events(
                            Command(resume=request.resume),
                            config, version="v2",
                        ),
                        session_id,
                    ):
                        if http_request and await http_request.is_disconnected():
                            return
                        yield sse_line
                else:
                    # 正常流
                    async for sse_line in adapt_langgraph_stream(
                        root_app.astream_events(
                            initial_state, config, version="v2",
                        ),
                        session_id,
                    ):
                        if http_request and await http_request.is_disconnected():
                            return
                        yield sse_line
                return

            # ━━━ 旧路径：ReAct 循环（Phase 2 替换为通用对话子图） ━━━
            async for event in agent.chat(
                session_id=request.session_id,
                user_message=question,
                attachments=[a.model_dump() for a in request.attachments] if request.attachments else None,
            ):
                # 客户端断开时 yield 会抛 CancelledError，中断整轮 ReAct 循环，
                # 避免 LLM 继续跑完整轮浪费 token
                if http_request and await http_request.is_disconnected():
                    logger.info("SSE客户端断开，中断Agent生成 session=%s", request.session_id)
                    return
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
    """上传文件到按用户隔离的临时目录，供聊天中使用。

    路径格式：TEMP_UPLOAD_DIR/{user_id}/{file_id}
    - 用户隔离：避免 file_id 跨用户访问（虽然当前 LLM 不会跨用户传，但防御性写法）
    - 启动时清理过期文件（参见 main.py 的 _cleanup_temp_uploads）
    """
    user_dir = os.path.join(settings.TEMP_UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件过大")

    file_id = str(uuid.uuid4())
    # 保留原始文件扩展名，避免后续 guess_extension 无法识别 Word/Excel 等格式
    original_ext = ""
    if file.filename and "." in file.filename:
        original_ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    file_path = os.path.join(user_dir, file_id + original_ext)

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
