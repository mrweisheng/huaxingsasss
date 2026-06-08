"""
ContractAgent — LangGraph 编排下的会话/消息/模式上下文服务器。

ReAct 循环已移除（PR-R-3 之后由 LangGraph root graph 接手），当下该服务器只负责：
  - 会话管理（create/list/delete session）
  - 消息结果录入 chat_history 表（finalize_node 调用 _save_message / save_tool_message）
  - mode / session_context 加载（api/v1/agent.py 用于 root graph 的 executor_mode 注入）
"""
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.ai.tools import ToolExecutor
from app.config import settings
from app.models.chat_history import ChatHistory
from app.models.chat_session import ChatSession
from app.models.user import User

logger = logging.getLogger(__name__)


class ContractAgent:
    """会话/消息/模式上下文服务器。

    不再提供 ReAct 循环服务（PR-R-3 已移除）。实际工具并发和 LLM 调用现在由
    app.ai.orchestrator.* 中的 LangGraph root graph 负责，服务器为其提供轻量的
    chat_history 上下文。
    """

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.executor = ToolExecutor(db, user)
        self._mode: str = "chat"
        self._session_context: Optional[dict] = None

    # ------------------------------------------------------------------
    # mode / session_context
    # ------------------------------------------------------------------

    def _load_session_meta(self, session_id: str) -> None:
        """从 chat_sessions 表加载 mode 和 context，注入到 self._mode / self._session_context。

        api/v1/agent.py 调用此方法确保 root graph 接收到用户的 mode 和 session_context。
        """
        session_record = (
            self.db.query(ChatSession)
            .filter(ChatSession.session_id == session_id)
            .first()
        )
        if session_record:
            self._mode = session_record.mode or "chat"
            self._session_context = session_record.context
        else:
            self._mode = "chat"
            self._session_context = None

    # ------------------------------------------------------------------
    # chat_history 上下文（finalize_node 调用）
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_messages(messages: List[dict]) -> str:
        """将消息列表序列化为纯文本，供摘要模型使用。

        标注：旧 ReAct 时使用。目前已无调用方。
        """
        lines = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "") or ""
            if role == "user":
                lines.append(f"用户: {content[:500]}")
            elif role == "assistant":
                tool_calls = m.get("tool_calls")
                if tool_calls:
                    tools_desc = ", ".join(
                        tc.get("function", {}).get("name", "") for tc in tool_calls
                    )
                    lines.append(f"助手(调用工具: {tools_desc}): {content[:500]}")
                else:
                    lines.append(f"助手: {content[:500]}")
            elif role == "tool":
                lines.append(f"工具结果: {content[:300]}")
        return "\n".join(lines)

    def _save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[list] = None,
        metadata: Optional[dict] = None,
        tokens_used: int = 0,
    ):
        """保存消息到 chat_history 表，由 finalize_node 调用。"""
        question = content if role == "user" else ""
        answer = None if role == "user" else content

        record = ChatHistory(
            user_id=self.user.id,
            session_id=session_id,
            question=question,
            answer=answer,
            role=role,
            tool_calls=tool_calls,
            extra_metadata=metadata or {},
            llm_model=settings.SILICONFLOW_AGENT_MODEL,
            tokens_used=tokens_used or None,
        )
        self.db.add(record)
        self.db.commit()

    def save_tool_message(
        self,
        session_id: str,
        tool_call_id: str,
        tool_name: str,
        result: str,
    ):
        """保存工具调用结果消息，由 finalize_node 调用。"""
        record = ChatHistory(
            user_id=self.user.id,
            session_id=session_id,
            question="",
            answer=result,
            role="tool",
            intent_type=tool_name,
            extra_metadata={"tool_call_id": tool_call_id},
            llm_model=settings.SILICONFLOW_AGENT_MODEL,
        )
        self.db.add(record)
        self.db.commit()

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    def get_sessions(self) -> List[dict]:
        """获取用户的所有会话列表（2 次查询替代 N+1）。"""
        from sqlalchemy import func as sa_func

        # Query 1: 聚合查询 — 每会话的消息数和最后活动时间
        aggregates = (
            self.db.query(
                ChatHistory.session_id,
                sa_func.count(ChatHistory.id).label("message_count"),
                sa_func.max(ChatHistory.created_at).label("last_activity"),
            )
            .filter(ChatHistory.user_id == self.user.id)
            .group_by(ChatHistory.session_id)
            .all()
        )

        session_ids = [s.session_id for s in aggregates]

        # Query 2: 批量读 chat_sessions 的 mode / title / context / created_at
        session_meta_map: dict = {}
        if session_ids:
            meta_records = (
                self.db.query(
                    ChatSession.session_id,
                    ChatSession.mode,
                    ChatSession.title,
                    ChatSession.context,
                    ChatSession.created_at,
                )
                .filter(ChatSession.session_id.in_(session_ids))
                .all()
            )
            for r in meta_records:
                session_meta_map[r.session_id] = {
                    "mode": r.mode,
                    "title": r.title,
                    "context": r.context,
                    "created_at": r.created_at,
                }

        # Query 3: 取每会话首条用户消息作标题（使用窗口函数）
        first_msg_map: dict = {}
        if session_ids:
            subq = (
                self.db.query(
                    ChatHistory.session_id,
                    ChatHistory.question,
                    sa_func.row_number().over(
                        partition_by=ChatHistory.session_id,
                        order_by=ChatHistory.created_at,
                    ).label("rn"),
                )
                .filter(
                    ChatHistory.user_id == self.user.id,
                    ChatHistory.role == "user",
                    ChatHistory.session_id.in_(session_ids),
                )
                .subquery()
            )
            first_msgs = (
                self.db.query(subq.c.session_id, subq.c.question)
                .filter(subq.c.rn == 1)
                .all()
            )
            for sid, question in first_msgs:
                first_msg_map[sid] = question[:50] if question else None

        result = []
        for s in aggregates:
            meta = session_meta_map.get(s.session_id, {})
            created = meta.get("created_at") or s.last_activity
            result.append({
                "session_id": s.session_id,
                "created_at": created.isoformat() if created else None,
                "message_count": s.message_count,
                "title": meta.get("title") or first_msg_map.get(s.session_id),
                "mode": meta.get("mode", "chat"),
                "context": meta.get("context"),
            })

        result.sort(key=lambda x: x["created_at"] or "", reverse=True)
        return result

    def get_history(self, session_id: str) -> List[dict]:
        """获取会话历史，并合并 tool 结果到 assistant 消息的 toolCalls 中。"""
        records = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.session_id == session_id,
                ChatHistory.user_id == self.user.id,
            )
            .order_by(ChatHistory.created_at.asc())
            .all()
        )

        tool_results = {}
        for r in records:
            if r.role == "tool" and r.extra_metadata:
                tool_call_id = r.extra_metadata.get("tool_call_id", "")
                if tool_call_id and r.answer:
                    tool_results[tool_call_id] = r.answer

        result = []
        for r in records:
            if r.role == "tool":
                continue

            msg = {
                "id": r.id,
                "role": r.role,
                "content": r.question if r.role == "user" else r.answer,
                "intent_type": r.intent_type,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }

            if r.role == "assistant" and r.tool_calls:
                merged_tool_calls = []
                for tc in r.tool_calls:
                    tc_copy = dict(tc) if tc else {}
                    tc_id = tc_copy.get("id", "")
                    if tc_id and tc_id in tool_results:
                        tc_copy["result"] = tool_results[tc_id]
                    merged_tool_calls.append(tc_copy)
                msg["tool_calls"] = merged_tool_calls
            else:
                msg["tool_calls"] = r.tool_calls

            result.append(msg)

        return result

    def delete_session(self, session_id: str) -> bool:
        """删除会话及其所有消息。

        同时清理 chat_sessions 表中的元数据行（避免遗留孤儿 session_id）。
        """
        history_deleted = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.session_id == session_id,
                ChatHistory.user_id == self.user.id,
            )
            .delete()
        )
        session_deleted = 0
        if history_deleted:
            session_deleted = (
                self.db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id,
                    ChatSession.user_id == self.user.id,
                )
                .delete()
            )
            logger.info(
                "delete_session: history=%d session_row=%d session=%s",
                history_deleted, session_deleted, session_id[:8],
            )
        self.db.commit()
        return history_deleted > 0