"""
ContractAgent — 基于 ReAct 模式的智能业务助手
使用 DeepSeek API 进行函数调用，SiliconFlow VL 模型处理图片
"""
import asyncio
import json
import logging
import os
import time
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

        logger.info(
            "Agent会话: session=%s, user=%s(%s), 附件=%d, 消息=%s",
            session_id[:8], self.user.username, self.user.role,
            len(attachments) if attachments else 0,
            user_message[:100],
        )

        # 1. 处理附件
        file_context = ""
        if attachments:
            yield {"event": "thinking", "data": {"message": f"正在分析 {len(attachments)} 个文件..."}}
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
            logger.info(
                "===== ReAct迭代 #%d 开始 | messages=%d 条 | session=%s =====",
                iteration, len(messages), session_id[:8],
            )

            # 调用 LLM
            full_text = ""
            tool_calls: List[dict] = []
            llm_event_count = 0

            try:
                logger.info("ReAct迭代 #%d: 开始调用 DeepSeek API...", iteration)
                async for event in self.llm.chat_completion_stream(
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                ):
                    llm_event_count += 1
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
                        logger.info(
                            "ReAct迭代 #%d: LLM流结束 | reason=%s | text_len=%d | tool_calls=%d | events=%d",
                            iteration, event.get("finish_reason"), len(full_text), len(tool_calls), llm_event_count,
                        )
                        if event.get("finish_reason") == "tool_calls":
                            pass
                logger.info(
                    "ReAct迭代 #%d: LLM调用完成 | text_len=%d | tool_calls=%d | total_events=%d",
                    iteration, len(full_text), len(tool_calls), llm_event_count,
                )
            except Exception as e:
                logger.exception("ReAct迭代 #%d LLM调用异常", iteration)
                # 如果之前有工具结果，用工具结果生成兜底回复
                fallback = self._build_tool_result_fallback(messages)
                full_text = fallback or f"抱歉，我在处理时遇到了技术问题: {str(e)}"
                yield {"event": "text", "data": {"content": full_text}}
                tool_calls = []

            logger.info(
                "===== ReAct迭代 #%d 结束 | text_len=%d | tool_calls=%d =====",
                iteration, len(full_text), len(tool_calls),
            )

            if not tool_calls:
                # 无工具调用，对话结束
                if not full_text.strip() and iteration > 0:
                    # 第二轮及以上返回空文本 → 尝试从最近的工具结果生成兜底回复
                    fallback = self._build_tool_result_fallback(messages)
                    if fallback:
                        full_text = fallback
                        logger.info("使用兜底回复: %s", full_text[:100])
                        yield {"event": "text", "data": {"content": full_text}}

                self._save_message(session_id, "assistant", full_text, tokens_used=total_tokens)
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

                _tool_start = time.monotonic()
                result = await asyncio.to_thread(self.executor.execute, tc["name"], args)
                _tool_elapsed = time.monotonic() - _tool_start
                logger.info(
                    "工具执行耗时: %s → %.1fs", tc["name"], _tool_elapsed,
                )

                logger.info(
                    "Agent工具结果: %s → %s", tc["name"],
                    result[:200] if result else "empty",
                )

                yield {
                    "event": "tool_result",
                    "data": {"name": tc["name"], "result": result[:6000]},
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
        full_text += "\n\n[系统提示：对话轮次已达上限，如果问题尚未解决，请继续提问。]"
        self._save_message(session_id, "assistant", full_text, tokens_used=total_tokens)
        yield {
            "event": "done",
            "data": {"session_id": session_id, "tokens_used": total_tokens},
        }

    async def _process_attachments(self, attachments: List[dict]) -> str:
        """处理附件：只返回文件标识信息，不预分析。
        LLM 会根据 system prompt 指引自已调用 analyze_image 工具，
        选择正确的 analysis_type（contract/receipt/general）。"""
        results = []
        for att in attachments:
            file_id = att.get("file_id", "")
            results.append(f"用户上传了文件（file_id: {file_id}）")
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
                tool_call_id = r.extra_metadata.get("tool_call_id", "") if r.extra_metadata else ""
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": r.answer or "",
                })

        # 校验并修复消息链：确保每个 tool 消息前有对应的 assistant(tool_calls)，
        # 且每个 assistant(tool_calls) 后有完整的 tool 回复
        return self._validate_message_chain(messages, session_id)

    @staticmethod
    def _validate_message_chain(messages: List[dict], session_id: str) -> List[dict]:
        """校验并修复消息链，确保 tool_calls/tool 配对完整。
        规则：
        1. tool 消息前必须是带 tool_calls 的 assistant
        2. assistant 带 tool_calls 时，紧跟的 tool 回复必须齐全
        """
        if not messages:
            return messages

        cleaned = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # 收集紧跟的 tool 回复
                tc_ids = {tc["id"] for tc in msg["tool_calls"]}
                tool_replies = []
                j = i + 1
                while j < len(messages) and messages[j].get("role") == "tool":
                    tool_replies.append(messages[j])
                    j += 1

                provided_ids = {t.get("tool_call_id", "") for t in tool_replies}
                if tc_ids.issubset(provided_ids):
                    # 配对完整，保留 assistant + 对应的 tool 回复
                    cleaned.append(msg)
                    cleaned.extend(tool_replies)
                else:
                    # 配对不完整，去掉 tool_calls，只保留 assistant 文本
                    logger.warning(
                        "截断不完整 tool_calls: session=%s, expected=%s, got=%s",
                        session_id[:8], tc_ids, provided_ids,
                    )
                    cleaned.append({"role": "assistant", "content": msg.get("content") or ""})
                i = j

            elif msg.get("role") == "tool":
                # 孤立 tool 消息（前面不是带 tool_calls 的 assistant），跳过
                logger.warning(
                    "跳过孤立 tool 消息: session=%s, tool_call_id=%s",
                    session_id[:8], msg.get("tool_call_id", ""),
                )
                i += 1

            else:
                cleaned.append(msg)
                i += 1

        return cleaned

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
    def _build_tool_result_fallback(messages: List[dict]) -> str:
        """当 LLM 在工具调用后未生成回复时，从最近的 tool 结果构建兜底回复"""
        # 查找最后一个 tool 消息
        for msg in reversed(messages):
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if not content:
                    continue
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and data.get("success"):
                        d = data.get("data", {})
                        if "document_type" in d:
                            # 凭证分析结果
                            parts = ["文件分析完成，以下是提取的关键信息："]
                            if d.get("document_type"):
                                parts.append(f"凭证类型: {d['document_type']}")
                            if d.get("amount"):
                                cur = d.get("currency", "")
                                parts.append(f"金额: {d['amount']} {cur}".strip())
                            if d.get("transaction_date"):
                                parts.append(f"日期: {d['transaction_date']}")
                            if d.get("payer_name"):
                                parts.append(f"付款人: {d['payer_name']}")
                            if d.get("payee_name"):
                                parts.append(f"收款人: {d['payee_name']}")
                            if d.get("transaction_id"):
                                parts.append(f"流水号: {d['transaction_id']}")
                            return "\n".join(parts)
                        if "content" in d and isinstance(d["content"], str):
                            # 文档内容
                            return f"文件分析完成，内容摘要：\n{d['content'][:1000]}"
                        if "contract_number" in d or "title" in d:
                            # 合同分析结果
                            parts = ["合同分析完成，以下是提取的关键信息："]
                            if d.get("title"):
                                parts.append(f"合同标题: {d['title']}")
                            if d.get("contract_number"):
                                parts.append(f"合同编号: {d['contract_number']}")
                            if d.get("party_b", {}).get("name"):
                                parts.append(f"客户: {d['party_b']['name']}")
                            if d.get("total_amount"):
                                cur = d.get("currency", "")
                                parts.append(f"总金额: {d['total_amount']} {cur}".strip())
                            return "\n".join(parts)
                except (json.JSONDecodeError, TypeError):
                    pass
                # 纯文本工具结果
                preview = content[:500]
                if len(content) > 500:
                    preview += "..."
                return f"工具执行完成，返回结果：\n{preview}"

        return ""

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
        tokens_used: int = 0,
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
