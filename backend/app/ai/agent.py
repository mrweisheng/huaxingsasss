"""
ContractAgent — 基于 ReAct 模式的智能业务助手
使用 DeepSeek API 进行函数调用，SiliconFlow VL 模型处理图片
"""
import json
import logging
import os
import uuid
from datetime import datetime, date
from typing import AsyncGenerator, Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.ai.llm_client import DeepSeekClient
from app.ai.prompts import (
    build_system_prompt,
    RECEIPT_ANALYSIS_PROMPT,
    CONTRACT_ANALYSIS_PROMPT,
    GENERAL_ANALYSIS_PROMPT,
    SUMMARY_PROMPT,
)
from app.ai.tools import ToolExecutor, TOOL_DEFINITIONS
from app.config import settings
from app.models.chat_history import ChatHistory
from app.models.user import User

logger = logging.getLogger(__name__)


class ContractAgent:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.llm = DeepSeekClient()
        self.executor = ToolExecutor(db, user)

    async def chat(
        self,
        session_id: Optional[str],
        user_message: str,
        attachments: Optional[List[dict]] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        主对话方法，SSE 流式输出。

        Yields:
            {"event": "text", "data": {"content": "..."}}
            {"event": "tool_call", "data": {"name": "...", "arguments": ...}}
            {"event": "tool_result", "data": {"name": "...", "result": "..."}}
            {"event": "thinking", "data": {"message": "..."}}
            {"event": "done", "data": {"session_id": "...", "tokens_used": ...}}
        """
        # 创建或复用会话
        if not session_id:
            session_id = str(uuid.uuid4())

        # 先处理附件，再保存消息（确保 file_context 写入数据库）
        file_context = ""
        if attachments:
            file_context = await self._process_attachments(attachments)
            yield {"event": "thinking", "data": {"message": "文件分析完成"}}

        self._save_message(session_id, "user", user_message, metadata={
            "attachments": attachments,
            "file_context": file_context,
        })

        # 加载对话历史（当前用户消息已含 file_context）
        history = self._load_history(session_id)

        # 构建消息
        messages = self._build_messages(history, user_message, file_context)

        # ReAct 循环
        total_tokens = 0
        for iteration in range(settings.AGENT_MAX_ITERATIONS):
            # 调用 LLM
            full_text = ""
            tool_calls: List[dict] = []

            async for event in self.llm.chat_completion_stream(
                messages=messages,
                tools=TOOL_DEFINITIONS,
            ):
                if event["type"] == "text":
                    full_text += event["content"]
                    yield {"event": "text", "data": {"content": event["content"]}}

                elif event["type"] == "tool_call":
                    tool_calls.append({
                        "id": event["id"],
                        "name": event["name"],
                        "arguments": event["arguments"],
                    })

                elif event["type"] == "usage":
                    total_tokens += event.get("total_tokens", 0)

                elif event["type"] == "done":
                    if event.get("finish_reason") == "tool_calls":
                        pass

            if not tool_calls:
                # 无工具调用，对话结束
                self._save_message(session_id, "assistant", full_text)
                yield {
                    "event": "done",
                    "data": {
                        "session_id": session_id,
                        "tokens_used": total_tokens,
                    },
                }
                return

            # 执行工具调用
            # 先把助手的工具调用消息加入上下文
            assistant_msg = {"role": "assistant", "content": full_text or None}
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                }
                for tc in tool_calls
            ]
            messages.append(assistant_msg)

            for tc in tool_calls:
                yield {
                    "event": "tool_call",
                    "data": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                }

                # 执行工具
                try:
                    args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
                except json.JSONDecodeError:
                    args = {}

                result = self.executor.execute(tc["name"], args)

                yield {
                    "event": "tool_result",
                    "data": {"name": tc["name"], "result": result[:2000]},
                }

                # 工具结果加入上下文
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            # 继续循环，让 LLM 根据工具结果生成回复

        # 超过最大迭代次数
        self._save_message(session_id, "assistant", full_text)
        yield {
            "event": "done",
            "data": {"session_id": session_id, "tokens_used": total_tokens},
        }

    async def _process_attachments(self, attachments: List[dict]) -> str:
        """处理附件（图片/PDF/Word/Excel/文本），返回分析结果的文本描述"""
        logger.info("[PROCESS_ATTACHMENTS] 开始处理 %d 个附件", len(attachments))
        results = []
        for i, att in enumerate(attachments):
            file_id = att.get("file_id", "")
            file_type = att.get("file_type", "image")

            logger.info("[PROCESS_ATTACHMENTS] 处理附件[%d]: file_id=%s, file_type=%s", i, file_id, file_type)

            file_path = os.path.join(settings.TEMP_UPLOAD_DIR, file_id)
            logger.info("[PROCESS_ATTACHMENTS]   文件路径: %s", file_path)
            logger.info("[PROCESS_ATTACHMENTS]   文件存在: %s", os.path.exists(file_path))

            if os.path.exists(file_path):
                try:
                    size = os.path.getsize(file_path)
                    logger.info("[PROCESS_ATTACHMENTS]   文件大小: %d bytes", size)
                except Exception as e:
                    logger.warning("[PROCESS_ATTACHMENTS]   获取文件大小失败: %s", e)
            else:
                logger.warning("[PROCESS_ATTACHMENTS]   文件不存在! TEMP_UPLOAD_DIR=%s", settings.TEMP_UPLOAD_DIR)
                # 列出临时目录内容帮助调试
                try:
                    files = os.listdir(settings.TEMP_UPLOAD_DIR)
                    logger.info("[PROCESS_ATTACHMENTS]   临时目录内容: %s", files)
                except Exception:
                    pass
                results.append(f"文件 {file_id} 不存在")
                continue

            # 统一使用 ToolExecutor.analyze_image 处理所有文件类型
            try:
                logger.info("[PROCESS_ATTACHMENTS]   调用 analyze_image(file_id=%s, analysis_type=general)", file_id)
                analysis_result = self.executor.analyze_image(file_id, analysis_type="general")
                logger.info("[PROCESS_ATTACHMENTS]   analyze_image 返回长度: %d", len(analysis_result))
                parsed = json.loads(analysis_result)
                logger.info("[PROCESS_ATTACHMENTS]   解析结果: success=%s, keys=%s", parsed.get("success"), list(parsed.keys()))
                if parsed.get("success"):
                    data = parsed.get("data", {})
                    file_type_label = parsed.get("file_type", file_type)
                    results.append(f"[{file_type_label} 文件分析结果] {json.dumps(data, ensure_ascii=False)}")
                else:
                    results.append(f"文件分析失败: {parsed.get('error', '未知错误')}")
            except json.JSONDecodeError:
                logger.warning("[PROCESS_ATTACHMENTS]   JSON 解析失败: %s", analysis_result[:200])
                results.append(f"文件分析结果解析失败: {analysis_result[:200]}")
            except Exception as e:
                logger.exception("[PROCESS_ATTACHMENTS] 附件分析异常 file_id=%s", file_id)
                results.append(f"文件分析异常: {str(e)}")

        logger.info("[PROCESS_ATTACHMENTS] 处理完成，返回 %d 条结果", len(results))
        return "\n".join(results)

    def _load_history(self, session_id: str) -> List[dict]:
        """从数据库加载对话历史"""
        records = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.session_id == session_id,
                ChatHistory.user_id == self.user.id,
            )
            .order_by(ChatHistory.created_at.desc())
            .limit(settings.AGENT_HISTORY_WINDOW)
            .all()
        )
        records.reverse()

        messages = []
        for r in records:
            if r.role == "user":
                content = r.question
                meta = r.extra_metadata or {}
                if meta.get("file_context"):
                    content += f"\n\n[文件分析上下文]\n{meta['file_context']}"
                messages.append({"role": "user", "content": content})
            elif r.role == "assistant":
                msg = {"role": "assistant", "content": r.answer}
                if r.tool_calls:
                    msg["tool_calls"] = r.tool_calls
                messages.append(msg)
            elif r.role == "tool":
                messages.append({
                    "role": "tool",
                    "tool_call_id": r.extra_metadata.get("tool_call_id", "") if r.extra_metadata else "",
                    "content": r.answer or "",
                })

        return messages

    def _build_messages(
        self,
        history: List[dict],
        user_message: str,
        file_context: str = "",
    ) -> List[dict]:
        """构建完整的消息数组"""
        system = {
            "role": "system",
            "content": build_system_prompt(
                user_name=self.user.full_name or self.user.username,
                user_role=self.user.role,
                current_date=date.today().isoformat(),
            ),
        }

        messages = [system]

        # 历史（不包含当前用户消息，因为用户消息已经在最后一条）
        messages.extend(history)

        # 如果历史为空或最后一条不是当前消息，添加当前消息
        if file_context:
            full_content = f"{user_message}\n\n[文件分析上下文]\n{file_context}"
        else:
            full_content = user_message

        if not history or history[-1].get("role") != "user":
            messages.append({"role": "user", "content": full_content})
        elif file_context:
            # 当前用户消息已在历史中（_save_message 先于 _process_attachments），
            # 但不含 file_context，需要追加
            messages[-1]["content"] += f"\n\n[文件分析上下文]\n{file_context}"

        return messages

    def _save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[list] = None,
        metadata: Optional[dict] = None,
    ):
        """保存消息到数据库"""
        if role == "user":
            question = content
            answer = None
        else:
            question = ""
            answer = content

        record = ChatHistory(
            user_id=self.user.id,
            session_id=session_id,
            question=question,
            answer=answer,
            role=role,
            tool_calls=tool_calls,
            extra_metadata=metadata or {},
            llm_model=settings.DEEPSEEK_AGENT_MODEL,
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
        """保存工具调用结果消息"""
        record = ChatHistory(
            user_id=self.user.id,
            session_id=session_id,
            question="",
            answer=result,
            role="tool",
            intent_type=tool_name,
            extra_metadata={"tool_call_id": tool_call_id},
            llm_model=settings.DEEPSEEK_AGENT_MODEL,
        )
        self.db.add(record)
        self.db.commit()

    def get_sessions(self) -> List[dict]:
        """获取用户的所有会话列表（2 次查询替代 N+1）"""
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

        # Query 2: 取每会话首条用户消息作标题（使用窗口函数）
        first_msg_map: dict[str, Optional[str]] = {}
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
            result.append({
                "session_id": s.session_id,
                "created_at": s.last_activity.isoformat() if s.last_activity else None,
                "message_count": s.message_count,
                "title": first_msg_map.get(s.session_id),
            })

        result.sort(key=lambda x: x["created_at"] or "", reverse=True)
        return result

    def get_history(self, session_id: str) -> List[dict]:
        """获取会话历史"""
        records = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.session_id == session_id,
                ChatHistory.user_id == self.user.id,
            )
            .order_by(ChatHistory.created_at.asc())
            .all()
        )

        return [
            {
                "id": r.id,
                "role": r.role,
                "content": r.question if r.role == "user" else r.answer,
                "tool_calls": r.tool_calls,
                "intent_type": r.intent_type,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

    def delete_session(self, session_id: str) -> bool:
        """删除会话及其所有消息"""
        deleted = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.session_id == session_id,
                ChatHistory.user_id == self.user.id,
            )
            .delete()
        )
        self.db.commit()
        return deleted > 0
