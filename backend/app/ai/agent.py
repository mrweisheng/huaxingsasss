"""
ContractAgent — 基于 ReAct 模式的智能业务助手
使用 DeepSeek API 进行函数调用，SiliconFlow VL 模型处理图片
"""
import asyncio
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

        # 1. 处理附件
        file_context = ""
        if attachments:
            file_context = await self._process_attachments(attachments)
            yield {"event": "thinking", "data": {"message": "文件分析完成"}}

        # 2. 加载历史（当前消息还未保存，不会出现在历史中）
        history = self._load_history(session_id)

        # 3. 历史摘要（超过阈值时压缩早期消息）
        summary = await self._summarize_history(history)
        if summary:
            history = history[-settings.AGENT_MAX_SUMMARY_MESSAGES:]

        # 4. 构建消息
        messages = self._build_messages(history, user_message, file_context, summary=summary)

        # 5. 保存当前用户消息到数据库
        self._save_message(session_id, "user", user_message, metadata={
            "attachments": attachments,
            "file_context": file_context,
        })

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
            # 把助手的工具调用消息加入上下文
            tool_calls_serialized = [
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
            assistant_msg = {"role": "assistant", "content": full_text or None}
            assistant_msg["tool_calls"] = tool_calls_serialized
            messages.append(assistant_msg)

            # 持久化 assistant 的 tool_call 消息
            self._save_message(session_id, "assistant", full_text or "", tool_calls=tool_calls_serialized)

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

                result = await asyncio.to_thread(self.executor.execute, tc["name"], args)

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

                # 持久化 tool result 消息
                self.save_tool_message(session_id, tc["id"], tc["name"], result[:5000])

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
                analysis_result = await asyncio.to_thread(self.executor.analyze_image, file_id, analysis_type="general")
                logger.info("[PROCESS_ATTACHMENTS]   analyze_image 返回长度: %d", len(analysis_result))
                parsed = json.loads(analysis_result)
                logger.info("[PROCESS_ATTACHMENTS]   解析结果: success=%s, keys=%s", parsed.get("success"), list(parsed.keys()))
                if parsed.get("success"):
                    data = parsed.get("data", {})
                    file_type_label = parsed.get("file_type", file_type)
                    results.append(f"[{file_type_label} 文件分析结果] file_id={file_id}\n{json.dumps(data, ensure_ascii=False)}")
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
        """从数据库加载对话历史（上限 100 条，用于摘要和上下文构建）"""
        records = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.session_id == session_id,
                ChatHistory.user_id == self.user.id,
            )
            .order_by(ChatHistory.created_at.desc())
            .limit(100)
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
        summary: Optional[str] = None,
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

        # 摘要注入（如有）
        if summary:
            messages.append({
                "role": "system",
                "content": f"[对话历史摘要]\n{summary}",
            })

        # 历史消息
        messages.extend(history)

        # 当前用户消息
        if file_context:
            full_content = f"{user_message}\n\n[文件分析上下文]\n{file_context}"
        else:
            full_content = user_message
        messages.append({"role": "user", "content": full_content})

        return messages

    async def _summarize_history(self, messages: List[dict]) -> Optional[str]:
        """当历史超过阈值时，将早期消息压缩为摘要保留关键业务信息"""
        keep_recent = settings.AGENT_MAX_SUMMARY_MESSAGES
        if len(messages) <= keep_recent + 4:
            return None

        older = messages[:-keep_recent]
        if len(older) < 4:
            return None

        history_text = self._serialize_messages(older)
        prompt = SUMMARY_PROMPT.format(history=history_text)

        try:
            summary_parts = []
            async for event in self.llm.chat_completion_stream(
                messages=[{"role": "user", "content": prompt}],
                tools=None,
                temperature=0.1,
                max_tokens=500,
            ):
                if event["type"] == "text":
                    summary_parts.append(event["content"])

            summary = "".join(summary_parts).strip()
            if summary:
                logger.info("历史摘要生成成功，%d 条早期消息压缩为 %d 字", len(older), len(summary))
            return summary or None
        except Exception as e:
            logger.warning("历史摘要生成失败，降级为完整历史: %s", e)
            return None

    @staticmethod
    def _serialize_messages(messages: List[dict]) -> str:
        """将消息列表序列化为纯文本，供摘要模型使用"""
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
        """获取会话历史，并合并 tool 结果到 assistant 消息的 toolCalls 中"""
        records = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.session_id == session_id,
                ChatHistory.user_id == self.user.id,
            )
            .order_by(ChatHistory.created_at.asc())
            .all()
        )

        # 构建 tool_call_id -> result 的映射
        tool_results: dict[str, str] = {}
        for r in records:
            if r.role == "tool" and r.extra_metadata:
                tool_call_id = r.extra_metadata.get("tool_call_id", "")
                if tool_call_id and r.answer:
                    tool_results[tool_call_id] = r.answer

        # 过滤掉 role='tool' 的独立记录，将结果合并到 assistant 消息
        result = []
        for r in records:
            if r.role == "tool":
                continue  # 跳过 tool 记录，结果已合并到 assistant

            msg = {
                "id": r.id,
                "role": r.role,
                "content": r.question if r.role == "user" else r.answer,
                "intent_type": r.intent_type,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }

            # 处理 tool_calls，合并结果
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
