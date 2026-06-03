"""
ContractAgent — 基于 ReAct 模式的智能业务助手
使用 DashScope 百炼 DeepSeek-V4-Flash 进行函数调用，qwen3-vl-flash 视觉模型处理图片
"""
import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import date
from typing import AsyncGenerator, Optional, List, Dict, Any

import httpx
import redis as redis_lib

from sqlalchemy.orm import Session

from app.ai.llm_client import DashScopeAgentClient
from app.ai.prompts import (
    build_system_prompt,
    RECEIPT_ANALYSIS_PROMPT,
    CONTRACT_ANALYSIS_PROMPT,
    GENERAL_ANALYSIS_PROMPT,
    SUMMARY_PROMPT,
    INCREMENTAL_SUMMARY_PROMPT,
)
from app.ai.tools import ToolExecutor, TOOL_DEFINITIONS
from app.config import settings
from app.models.chat_history import ChatHistory
from app.models.user import User

logger = logging.getLogger(__name__)

# 工具名称 → 中文友好描述（用于前端 thinking 提示）
_TOOL_FRIENDLY_NAMES = {
    "get_overview": "查询全局统计",
    "search_customers": "搜索客户",
    "create_customer": "创建客户",
    "update_customer": "更新客户信息",
    "search_contracts": "搜索合同",
    "get_contract_detail": "获取合同详情",
    "get_customer_contracts": "查询客户合同",
    "create_contract": "创建合同",
    "update_contract": "更新合同信息",
    "query_payments": "查询付款记录",
    "create_payment": "创建收入记录",
    "create_expense": "创建支出记录",
    "update_payment": "更新付款记录",
    "match_receipt": "匹配凭证",
    "get_expense_summary": "汇总支出",
    "get_payment_summary": "汇总付款",
    "get_expiring_contracts": "查询即将到期合同",
    "search_contract_text": "搜索合同全文",
    "ask_contract": "查阅合同内容",
    "analyze_image": "分析文件",
}

# 用户确认意图匹配模式（re.IGNORECASE 已覆盖大小写变体）
# 严格枚举，不使用 .* 通配符，避免"好的但我需要改一下"被误判为确认
_CONFIRM_PATTERN = re.compile(
    r'^(好的|确认|没问题|可以|执行|对|是的|ok|yes|好|行|就这样|确认执行|'
    r'可以的|可以啊|可以吧|可以呢|'
    r'好的啊|好的吧|好的呢|'
    r'对啊|对的|对呢|'
    r'好啊|好吧|好呢|'
    r'行啊|行吧|行呢|'
    r'确认了|确认啦|执行吧|'
    r'没问题的|没问题了|没问题啦|'
    r'是的呢|是的吧|是的啦|'
    r'没错|好滴|好嘞|好咧|必须的|'
    r'需要的|要的|要啊|要吧|'
    r'当然|当然可以|当然好|就这样吧|就这样了)$',
    re.IGNORECASE,
)


class ContractAgent:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.llm = DashScopeAgentClient()
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

        # 将 session_id 注入 executor，供 DB 兜底查询使用
        self.executor.session_id = session_id

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

        # 3. 历史摘要（超过阈值时压缩早期消息，支持增量缓存）
        summary = await self._summarize_history(history, session_id=session_id)
        if summary:
            history = history[-settings.AGENT_MAX_SUMMARY_MESSAGES:]
            # 截断可能拆散 tool_call 配对，需重新验证
            history = self._validate_message_chain(history, session_id)
            # 进一步确保最后一轮 assistant+tool 配对完整，避免摘要窗口过短
            # 导致 LLM 看不到工具结果
            history = self._ensure_trailing_pair_intact(history)

        # 4. 确认意图快捷路径：检测用户是否在确认上一轮提出的操作
        if (
            not file_context  # 没有新附件
            and not attachments
            and self._is_confirmation(user_message)
            and self._last_assistant_asked_confirmation(history)
        ):
            logger.info("检测到用户确认意图，注入快捷信号: session=%s", session_id[:8])
            user_message = (
                f"[系统注入：用户已确认，请立即执行上一轮提出的操作，不要重复解释或再次确认]\n"
                f"用户说：「{user_message}」"
            )

        # 5. 构建消息
        messages = self._build_messages(history, user_message, file_context, summary=summary)

        # 6. 用户消息先入 messages（用于本轮 LLM 调用），
        #    但延迟到助手回复成功后再 commit，避免 LLM 失败时出现"用户问了 AI 没答"的孤儿用户消息。
        pending_user_metadata = {
            "attachments": attachments,
            "file_context": file_context,
        }

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

            # 调用前消毒消息链：移除可能存在的孤立 tool 消息
            messages = self._sanitize_messages_for_api(messages, session_id)

            try:
                logger.info("ReAct迭代 #%d: 开始调用 DashScope Agent API...", iteration)
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
                if fallback is not None:
                    full_text = fallback
                else:
                    full_text = f"抱歉，我在处理时遇到了技术问题: {str(e)}"
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
                    if fallback is not None:
                        full_text = fallback
                        logger.info("使用兜底回复: %s", full_text[:100])
                        yield {"event": "text", "data": {"content": full_text}}

                self._save_message(session_id, "assistant", full_text, tokens_used=total_tokens)
                # 助手消息落库成功后才落库用户消息，避免孤儿 user 消息
                self._save_message(session_id, "user", user_message, metadata=pending_user_metadata)
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
            # 注意：首轮写库时同步把用户消息也入库，确保 user/assistant 配对一致
            self._save_message(session_id, "assistant", full_text or "", tool_calls=tool_calls_serialized)
            if iteration == 0 and not getattr(self, "_user_msg_persisted", False):
                self._save_message(session_id, "user", user_message, metadata=pending_user_metadata)
                self._user_msg_persisted = True

            for tc in tool_calls:
                # 工具执行前通知前端
                _friendly = _TOOL_FRIENDLY_NAMES.get(tc["name"], tc["name"])
                yield {"event": "thinking", "data": {"message": f"正在{_friendly}..."}}

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

                # 持久化 tool result 消息（完整存储，缓存方案依赖完整 VL 输出）
                self.save_tool_message(session_id, tc["id"], tc["name"], result)

            # 继续循环，让 LLM 根据工具结果生成回复
            yield {"event": "thinking", "data": {"message": "正在整合结果..."}}

        # 超过最大迭代次数
        full_text += "\n\n[系统提示：对话轮次已达上限，如果问题尚未解决，请继续提问。]"
        self._save_message(session_id, "assistant", full_text, tokens_used=total_tokens)
        if not getattr(self, "_user_msg_persisted", False):
            self._save_message(session_id, "user", user_message, metadata=pending_user_metadata)
            self._user_msg_persisted = True
        yield {
            "event": "done",
            "data": {"session_id": session_id, "tokens_used": total_tokens},
        }

    async def _process_attachments(self, attachments: List[dict]) -> str:
        """处理附件：对文本型 PDF 直接预分析（跳过 LLM 决策层），其余返回文件标识交给 LLM 调 analyze_image。"""
        results = []
        for att in attachments:
            file_id = att.get("file_id", "")
            file_type = att.get("file_type", "")

            # 尝试预分析：文本型 PDF / Word / Excel 可直接用文本模型，不需要 LLM 中转
            pre_analyzed = await self._try_pre_analyze(file_id, file_type)
            if pre_analyzed:
                results.append(pre_analyzed)
            else:
                results.append(f"用户上传了文件（file_id: {file_id}）")

        return "\n".join(results)

    async def _try_pre_analyze(self, file_id: str, file_type: str) -> Optional[str]:
        """快速提取文本型文件内容（<1s），跳过慢的 ContractAnalyzer API 调用。
        文本型 PDF / Word / Excel：提取原文 → 查重 → 缓存 → 返回给 LLM。
        扫描件 PDF / 图片：返回 None，交给 LLM 调 analyze_image → VL 模型。"""
        if not file_id:
            return None

        # 解析文件路径（与 ContractAnalyzer.resolve_file_path 一致）
        candidates = [
            os.path.join(settings.TEMP_UPLOAD_DIR, str(self.user.id), file_id),
            os.path.join(settings.TEMP_UPLOAD_DIR, file_id),
        ]
        file_path = next((p for p in candidates if os.path.exists(p)), None)
        if not file_path:
            return None

        # 读取文件头判断类型
        try:
            with open(file_path, "rb") as f:
                header = f.read(2000)
        except OSError:
            return None

        from app.services.contract_analyzer import _is_docx, _is_xlsx

        text = ""
        file_type_label = ""

        if header[:4] == b"%PDF":
            # PDF：检测是否有可提取文字
            try:
                from app.services.contract_analyzer import _extract_pdf_text
                text = _extract_pdf_text(file_path)
            except Exception:
                return None
            if not text.strip():
                # 扫描件 PDF，交给 LLM 调 analyze_image → VL 模型
                return None
            file_type_label = "PDF"
        elif _is_docx(header):
            try:
                from app.services.contract_analyzer import _extract_word_text
                text = _extract_word_text(file_path)
            except Exception:
                return None
            if not text.strip():
                return None
            file_type_label = "Word"
        elif _is_xlsx(header):
            try:
                from app.services.contract_analyzer import _extract_excel_text
                text = _extract_excel_text(file_path)
            except Exception:
                return None
            if not text.strip():
                return None
            file_type_label = "Excel"
        else:
            # 图片或其他格式，交给 LLM 调 analyze_image
            return None

        # 快速查重：计算 hash + DB 查询（复用 ContractAnalyzer 的 hash 算法）
        try:
            from app.utils.file_utils import calculate_file_hash
            with open(file_path, "rb") as f:
                file_hash = calculate_file_hash(f.read())
            # 缓存 hash 供 create_contract 复用，避免重复读取大文件
            self.executor._file_hash_cache[file_path] = file_hash
            from app.models.contract import Contract
            existing = self.db.query(Contract).filter(
                Contract.file_hash == file_hash,
                Contract.is_deleted == False,
            ).first()
            if existing:
                return (
                    f"[系统预分析结果 - 文件重复]\n"
                    f"该文件已在系统中存在对应的合同记录。\n"
                    f"合同编号：{existing.contract_number}，客户：{existing.title or '未知'}，"
                    f"状态：{existing.status}。"
                )
        except Exception:
            logger.debug("查重跳过: file_id=%s", file_id)

        # ━━━ 调用 LLM 提取结构化数据 ← 保证 create_contract 始终有 payment_terms ━━━
        logger.info("预分析: 调用百炼DeepSeek-V4-Flash提取合同结构化数据, text_len=%d", len(text))
        try:
            from app.services.contract_analyzer import _make_text_extraction_prompt

            actual_prompt = _make_text_extraction_prompt(CONTRACT_ANALYSIS_PROMPT)
            payload = {
                "model": settings.DASHSCOPE_AGENT_MODEL,
                "messages": [{
                    "role": "user",
                    "content": f"{actual_prompt}\n\n以下是合同文件的文字内容，请提取结构化信息：\n\n{text[:8000]}",
                }],
                "temperature": 0.1,
                "max_tokens": 4096,
            }
            headers = {
                "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
                "Content-Type": "application/json",
            }
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{settings.DASHSCOPE_BASE_URL}/chat/completions",
                    json=payload, headers=headers,
                )

            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                try:
                    structured = json.loads(content)
                except json.JSONDecodeError:
                    structured = {"raw": content}

                if isinstance(structured, dict):
                    structured["full_text"] = text
                    self.executor._document_context = "contract"
                    self.executor._cache_analysis(file_id, "contract", structured)

                    # 构建结构化摘要返回给 Agent
                    summary_parts = []
                    if structured.get("party_b", {}).get("name"):
                        summary_parts.append(f"客户：{structured['party_b']['name']}")
                    if structured.get("total_amount"):
                        cur = structured.get("currency", "")
                        summary_parts.append(f"金额：{structured['total_amount']} {cur}".strip())
                    if structured.get("signed_date"):
                        summary_parts.append(f"签订日期：{structured['signed_date']}")
                    if structured.get("payment_terms"):
                        terms_str = "、".join(
                            f"{t.get('name', t.get('description', '?'))} {t.get('amount', '?')}"
                            for t in structured["payment_terms"]
                        )
                        summary_parts.append(f"付款条款：{terms_str}")
                    if structured.get("business_description"):
                        summary_parts.append(f"业务：{structured['business_description']}")

                    summary = "\n".join(summary_parts) if summary_parts else "合同结构化数据已提取"
                    logger.info("预分析完成: keys=%s", list(structured.keys()))
                    return (
                        f"[系统已自动提取合同结构化数据，请勿再调用 analyze_image 工具]\n"
                        f"文件类型：{file_type_label}\n"
                        f"file_id：{file_id}\n"
                        f"提取摘要：\n{summary}\n\n"
                        f"完整原文（共{len(text)}字符）：\n{text[:2000]}"
                        f"{'...' if len(text) > 2000 else ''}\n\n"
                        f"请基于以上摘要向用户展示关键信息（客户、金额、付款条款），询问是否需要创建合同。"
                    )
                else:
                    logger.warning("预分析: LLM 返回非 dict，降级为 raw_text 缓存")
            else:
                logger.warning(
                    "预分析: LLM 调用失败 status=%s body=%s，降级为 raw_text 缓存",
                    response.status_code, response.text[:200],
                )
        except Exception:
            logger.exception("预分析: LLM 调用异常，降级为 raw_text 缓存")

        # ━━━ 降级路径：LLM 失败时缓存原文（create_contract 需 raw_text）━━━
        self.executor._document_context = "contract"
        self.executor._cache_analysis(file_id, "contract", {
            "raw_text": text,
            "file_type": file_type_label,
        })

        # 截断原文给 LLM，完整原文通过缓存供 create_contract 使用
        context_str = text[:8000]
        if len(text) > 8000:
            context_str += f"\n\n...（共 {len(text)} 字符，已截断）"

        return (
            f"[系统已自动提取文件内容，请勿再调用 analyze_image 工具]\n"
            f"文件类型：{file_type_label}\n"
            f"file_id：{file_id}\n"
            f"提取内容：\n{context_str}\n\n"
            f"请直接基于以上内容向用户展示关键信息，询问是否需要创建合同。"
        )

    @staticmethod
    def _is_confirmation(user_message: str) -> bool:
        """判断用户消息是否为确认意图（短文本 + 匹配确认模式）"""
        stripped = user_message.strip()
        if not stripped or len(stripped) > 30:
            return False
        return bool(_CONFIRM_PATTERN.match(stripped))

    @staticmethod
    def _last_assistant_asked_confirmation(history: List[dict]) -> bool:
        """检查最近一条 assistant 消息是否在请求用户确认"""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if not content:
                    continue
                # 检查是否包含确认请求的典型措辞
                confirm_keywords = (
                    "确认", "是否", "要关联", "关联吗", "要创建", "创建吗",
                    "是否需要", "需要吗", "执行吗", "是否将", "将.*关联",
                    "确认后", "请确认", "确认一下",
                )
                return bool(re.search("|".join(confirm_keywords), content))
        return False

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

    @staticmethod
    def _ensure_trailing_pair_intact(messages: List[dict]) -> List[dict]:
        """如果历史以 assistant(tool_calls) 开头但缺少对应 tool 回复，
        说明截断拆散了配对。回退一格找到完整的最后一轮工具配对。
        """
        if not messages:
            return messages
        last = messages[-1]
        if last.get("role") == "assistant" and last.get("tool_calls"):
            # 向前找最近的 user 消息，确保包含完整一轮
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    return messages[i:]
            # 没有 user 兜底：剥离末尾的 tool_calls
            return [{"role": "assistant", "content": last.get("content") or ""}]
        return messages

    @staticmethod
    def _sanitize_messages_for_api(messages: List[dict], session_id: str) -> List[dict]:
        """最终消毒：确保发送给 LLM 的消息链没有孤立 tool 消息。

        规则：每个 tool 消息必须跟在带匹配 tool_calls 的 assistant 后面，
        否则移除。同时也会移除 tool_calls 后缺失 tool 回复的 assistant。
        """
        if not messages:
            return messages

        sanitized: List[dict] = []
        expected_tool_ids: set = set()  # 当前期待的 tool_call_id 集合

        for msg in messages:
            if msg.get("role") == "assistant":
                sanitized.append(msg)
                if msg.get("tool_calls"):
                    expected_tool_ids = {tc["id"] for tc in msg["tool_calls"] if tc.get("id")}
                else:
                    expected_tool_ids = set()

            elif msg.get("role") == "tool":
                tc_id = msg.get("tool_call_id", "")
                if tc_id and tc_id in expected_tool_ids:
                    sanitized.append(msg)
                    expected_tool_ids.discard(tc_id)
                else:
                    logger.warning(
                        "API消毒: 跳过孤立 tool 消息: session=%s, tool_call_id=%s",
                        session_id[:8], tc_id,
                    )

            else:
                sanitized.append(msg)

        # 如果 sanitized 后最后一个消息是带 tool_calls 的 assistant（缺少 tool 回复），
        # 剥离 tool_calls 避免 API 拒绝
        if sanitized:
            last = sanitized[-1]
            if last.get("role") == "assistant" and last.get("tool_calls"):
                logger.warning(
                    "API消毒: 剥离末尾不完整 tool_calls: session=%s, tool_calls=%s",
                    session_id[:8], [tc.get("id", "") for tc in last["tool_calls"]],
                )
                sanitized[-1] = {"role": "assistant", "content": last.get("content") or ""}

        return sanitized

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

    async def _summarize_history(self, messages: List[dict], session_id: str = "") -> Optional[str]:
        """当历史超过阈值时，将早期消息压缩为摘要保留关键业务信息。
        支持增量更新：优先从 Redis 读取缓存摘要，仅将新增消息合并进已有摘要。
        """
        keep_recent = settings.AGENT_MAX_SUMMARY_MESSAGES
        if len(messages) <= keep_recent + 4:
            return None

        older = messages[:-keep_recent]
        if len(older) < 4:
            return None

        older_count = len(older)

        # 尝试读取缓存摘要
        cached = self._get_cached_summary(session_id)
        if cached and cached.get("msg_count") == older_count:
            # 完全一致，直接复用
            logger.debug("摘要缓存命中（完全一致）: session=%s, count=%d", session_id[:8], older_count)
            return cached["summary"]

        if cached and cached.get("summary"):
            delta_count = older_count - cached["msg_count"]
            if 0 < delta_count < 10:
                # 增量更新：仅处理新增消息
                delta_messages = older[-delta_count:]
                summary = await self._incremental_summarize(cached["summary"], delta_messages)
                if summary:
                    self._cache_summary(session_id, older_count, summary)
                    return summary
                # 增量失败，降级全量

        # 全量生成（首次 / 缓存过期 / 增量失败）
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
                self._cache_summary(session_id, older_count, summary)
            return summary or None
        except Exception as e:
            logger.warning("历史摘要生成失败，降级为完整历史: %s", e)
            return None

    # ── 摘要缓存方法 ──────────────────────────────────────────

    _SUMMARY_CACHE_TTL = 7200  # 2 小时

    def _get_redis(self) -> Optional[redis_lib.Redis]:
        """获取 Redis 连接（复用 executor 的连接）"""
        return getattr(self.executor, "_redis", None)

    def _get_cached_summary(self, session_id: str) -> Optional[dict]:
        """从 Redis 读取缓存摘要"""
        redis = self._get_redis()
        if not redis or not session_id:
            return None
        try:
            raw = redis.get(f"agent_summary:{session_id}")
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("summary"):
                    return data
        except Exception:
            logger.debug("摘要缓存读取失败: session=%s", session_id[:8])
        return None

    def _cache_summary(self, session_id: str, msg_count: int, summary: str) -> None:
        """将摘要写入 Redis 缓存"""
        redis = self._get_redis()
        if not redis or not session_id:
            return
        try:
            redis.setex(
                f"agent_summary:{session_id}",
                self._SUMMARY_CACHE_TTL,
                json.dumps({"summary": summary, "msg_count": msg_count}, ensure_ascii=False),
            )
        except Exception:
            logger.debug("摘要缓存写入失败: session=%s", session_id[:8])

    async def _incremental_summarize(self, cached_summary: str, delta_messages: List[dict]) -> Optional[str]:
        """基于已有摘要和新增消息做增量更新"""
        delta_text = self._serialize_messages(delta_messages)
        prompt = INCREMENTAL_SUMMARY_PROMPT.format(
            existing_summary=cached_summary,
            delta_messages=delta_text,
        )
        try:
            parts = []
            async for event in self.llm.chat_completion_stream(
                messages=[{"role": "user", "content": prompt}],
                tools=None,
                temperature=0.1,
                max_tokens=500,
            ):
                if event["type"] == "text":
                    parts.append(event["content"])
            summary = "".join(parts).strip()
            if summary:
                logger.info("摘要增量更新成功，%d 条新消息合并，摘要 %d 字", len(delta_messages), len(summary))
            return summary or None
        except Exception as e:
            logger.warning("摘要增量更新失败，降级全量: %s", e)
            return None

    def _build_tool_result_fallback(self, messages: List[dict]) -> Optional[str]:
        """当 LLM 在工具调用后未生成回复时，从最近的 tool 结果构建兜底回复。
        委托给 ToolExecutor.format_result_summary 处理。"""
        for msg in reversed(messages):
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if not content:
                    continue
                return self.executor.format_result_summary(content)
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
            llm_model=settings.DASHSCOPE_AGENT_MODEL,
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
            llm_model=settings.DASHSCOPE_AGENT_MODEL,
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
        """删除会话及其所有消息，同时清理关联 Redis 缓存"""
        deleted = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.session_id == session_id,
                ChatHistory.user_id == self.user.id,
            )
            .delete()
        )
        self.db.commit()
        if deleted > 0:
            self._cleanup_session_redis(session_id)
        return deleted > 0

    def _cleanup_session_redis(self, session_id: str) -> None:
        """清理会话关联的 Redis 缓存（VL 分析缓存 + 摘要缓存）"""
        redis = self._get_redis()
        if not redis:
            return
        try:
            # 清理 VL 分析缓存: vl:*:{session_id}:*
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match=f"vl:*:{session_id}:*", count=100)
                if keys:
                    redis.delete(*keys)
                if cursor == 0:
                    break
            # 清理摘要缓存
            redis.delete(f"agent_summary:{session_id}")
            logger.debug("会话 Redis 缓存已清理: session=%s", session_id[:8])
        except Exception:
            logger.debug("会话 Redis 清理失败（可忽略）: session=%s", session_id[:8])
