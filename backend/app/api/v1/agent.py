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
    logger.info("[AGENT CHAT] resume: %s", request.resume)
    logger.info("[AGENT CHAT] interrupt_id: %s", request.interrupt_id)
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

    agent = ContractAgent(db, current_user)

    async def event_generator():
        try:
            # ━━━ LangGraph 编排路径（唯一运行时） ━━━
            from app.ai.orchestrator.graph import build_root_graph
            from app.ai.orchestrator.contract_entry import ContractEntrySubgraph
            from app.ai.orchestrator.sse_adapter import adapt_langgraph_stream
            from app.ai.orchestrator.checkpointer import get_checkpointer

            # 中断恢复：基本校验
            if request.resume:
                if not request.interrupt_id or not isinstance(request.interrupt_id, str):
                    yield f"data: {json.dumps({'event': 'error', 'data': {'message': '中断恢复缺少有效的 interrupt_id'}}, ensure_ascii=False)}\n\n"
                    return

            try:
                cp = get_checkpointer()
            except RuntimeError as e:
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

            # 构建子图 + 根图。mode / session_context 通过构造函数注入到子图闭包
            # 内的 ToolExecutor。PR-B-4: 子图不再依赖 agent 实例（独立化）。
            # agent 仅注入到 build_root_graph 的 finalize_node 用于 chat_history 落库（ADR #6）。
            # 注意：必须在 interrupt_id 校验前构建，因为需要 root_app.aget_state()
            # 来获取 StateSnapshot（cp.aget 返回原始 dict，不含 .interrupts）。
            contract_entry = ContractEntrySubgraph(
                db, current_user,
                mode=agent._mode,
                session_context=agent._session_context,
                session_id=session_id,
            )
            contract_app = contract_entry.build()
            session_context = dict(agent._session_context or {})
            session_context["mode"] = agent._mode
            root_app = build_root_graph(
                contract_app,
                checkpointer=cp,
                agent=agent,
                db=db,
                user=current_user,
                session_context=session_context,
                session_id=session_id,
            )

            # ━━━ 中断恢复：校验 interrupt_id 与当前待处理中断匹配 ━━━
            #
            # 关键设计（修复版 v2）：
            #   1. sse_adapter._interrupt_from_list() 已将 LangGraph 内部分配的
            #      Interrupt.id（UUID）覆盖到 SSE payload 的 interrupt_id 字段。
            #      前端回传的 request.interrupt_id 就是这个 UUID。
            #   2. 因此校验时必须从 Interrupt.id（而非 value["interrupt_id"]）提取比对。
            #   3. 冷编译图（每次请求重建）的 aget_state() 在某些 LangGraph 版本中
            #      可能返回异常数据，因此内置两层兜底：
            #      a) 防御式 getattr（防止 dict 无 .interrupts 属性崩溃）
            #      b) 直接查询 checkpointer 获取 pending_writes 中的 interrupt
            if request.resume:
                pending_ids = []
                checkpoint_ok = False

                # ── 主路径：graph.aget_state() → StateSnapshot.interrupts ──
                try:
                    state_snapshot = await root_app.aget_state(config)
                    # 防御式：兼容 StateSnapshot 和原始 dict 两种返回类型
                    interrupts_raw = (
                        getattr(state_snapshot, 'interrupts', None) or []
                        if not isinstance(state_snapshot, dict)
                        else state_snapshot.get('interrupts', [])
                    )
                    for item in interrupts_raw:
                        lg_id = getattr(item, 'id', None)
                        if lg_id:
                            pending_ids.append(lg_id)
                    checkpoint_ok = True
                    logger.debug(
                        "checkpoint 查询成功(aget_state): pending_ids=%s thread=%s",
                        pending_ids, session_id,
                    )
                except Exception as e:
                    logger.warning(
                        "aget_state 查询异常（将尝试 fallback）: %s thread=%s",
                        e, session_id,
                    )

                # ── 兜底路径：直接查 checkpointer pending_writes ──
                if not checkpoint_ok:
                    try:
                        saved = await cp.aget_tuple(config)
                        if saved and saved.pending_writes:
                            for _tid, _chan, _val in saved.pending_writes:
                                if _chan in ("__interrupt__", "interrupt"):
                                    items = _val if isinstance(_val, (list, tuple)) else [_val]
                                    for it in items:
                                        lg_id = getattr(it, 'id', None)
                                        if lg_id:
                                            pending_ids.append(lg_id)
                        checkpoint_ok = True
                        logger.debug(
                            "checkpoint 查询成功(fallback): pending_ids=%s thread=%s",
                            pending_ids, session_id,
                        )
                    except Exception as e2:
                        logger.warning(
                            "checkpoint fallback 也失败，放行由 LangGraph 内部校验: %s thread=%s",
                            e2, session_id,
                        )
                        # 不 return，让 LangGraph 内部处理 resume 校验

                # ── 校验（仅在主路径或兜底路径成功时执行） ──
                if checkpoint_ok and pending_ids and request.interrupt_id not in pending_ids:
                    logger.warning(
                        "interrupt_id 不匹配: received=%s pending=%s thread=%s",
                        request.interrupt_id, pending_ids, session_id,
                    )
                    yield f"data: {json.dumps({'event': 'error', 'data': {'message': 'interrupt_id 不匹配当前待处理中断，请刷新页面重试'}}, ensure_ascii=False)}\n\n"
                    return
                logger.info(
                    "interrupt_id 校验通过: id=%s thread=%s",
                    request.interrupt_id, session_id,
                )

            # 构造 initial_state。auto_filled 标记透传到 HumanMessage.additional_kwargs，
            # finalize_node 读取后写入 chat_history.metadata，区分"用户实际输入"与"系统补全"
            from langchain_core.messages import HumanMessage
            initial_state = {
                "messages": [HumanMessage(
                    content=question,
                    additional_kwargs={"auto_filled": True} if auto_filled else {},
                )],
                "user_id": current_user.id,
                "user_role": current_user.role,
                "session_id": session_id,
                "executor_mode": agent._mode,
                "session_context": agent._session_context or {},
                "_finalized": False,  # 每轮新请求重置幂等标记，避免跨轮残留
                # Defense in depth：analyze 节点也会重置，这里再重置一次保证从入口
                # 进来时状态干净（防止 checkpoint 残留 should_end=True 导致
                # route_after_analyze 误判 END、Agent 循环进不去）
                "should_end": False,
                "iteration_count": 0,
            }
            # 仅在请求携带附件时才覆盖 checkpoint 中的 attachments，
            # 否则保留上一轮的附件上下文（支持多轮合同录入等场景）
            # 注意：无附件时必须显式置 []，否则 checkpoint 中旧 attachments 残留
            # 会导致 analyze 节点重新分析已处理过的文件（触发重复检测）。
            # analyze 节点通过 file_context（而非 attachments）判断是否续接。
            if request.attachments:
                initial_state["attachments"] = [a.model_dump() for a in request.attachments]
            else:
                initial_state["attachments"] = []

            if request.resume:
                # 中断恢复（校验已在上方完成）
                from langgraph.types import Command
                async for sse_line in adapt_langgraph_stream(
                    root_app.astream_events(
                        Command(resume=request.resume),
                        config, version="v2",
                    ),
                    session_id,
                    graph=root_app,
                    config=config,
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
                    graph=root_app,
                    config=config,
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
