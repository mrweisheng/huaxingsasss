"""LangGraph astream_events -> 现有 SSE 事件格式适配器

文档 6.8：LangGraph 事件 -> SSE 事件映射表
Phase 1 新增 interrupt 事件类型

关键设计：astream_events 生成器在子图 interrupt() 处可能阻塞（节点等待 resume
不 yield 事件），因此用后台任务 + 队列解耦消费，主循环定期轮询图检查点
检测 interrupt，避免前端永久转圈。
"""
import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional, FrozenSet

from app.ai.orchestrator.state import RootState

logger = logging.getLogger(__name__)


async def adapt_langgraph_stream(
    agen,  # AsyncGenerator from astream_events
    session_id: str,
    graph=None,    # CompiledGraph，用于 interrupt 后检查 checkpoint
    config=None,   # graph config，含 thread_id
) -> AsyncGenerator[str, None]:
    """将 LangGraph astream_events 流转换为现有 SSE 事件格式。

    核心机制：astream_events 在子图 interrupt() 时，节点阻塞等待 resume，
    生成器不再 yield 事件。通过后台任务消费生成器 + 主循环轮询检查点，
    可在节点阻塞时检测到 interrupt 并及时通知前端。

    Args:
        agen: graph.astream_events(initial_state, config, version="v2") 的返回
        session_id: 会话 ID
        graph: 编译后的图（可选），用于 aget_state 检查 interrupt
        config: 图配置（可选），含 configurable.thread_id

    Yields:
        "data: {json}\\n\\n" 格式的 SSE 字符串
    """
    # 用 list 在后台任务和主循环之间传递事件（asyncio 单线程，无需锁）
    collected_events: list = []
    stream_done = False
    stream_error: Optional[Exception] = None
    stream_done_event = asyncio.Event()  # 流结束时主动通知主循环，无需等 sleep 超时

    # 事件缓冲软上限：超过此值时让 _consume_stream 短暂让步，避免主循环卡顿时 OOM。
    # 50 = 5s × 10 evt/s（极端高速场景的 1 秒产量），给主循环充足窗口消费。
    _EVENT_BUFFER_SOFT_CAP = 500

    async def _consume_stream():
        """后台任务：消费 astream_events 生成器，事件存入 collected_events。
        事件数达到软上限时短暂 yield，避免主循环卡顿时 OOM。"""
        nonlocal stream_done, stream_error
        event_count = 0
        last_event_name = ""
        try:
            async for event in agen:
                event_count += 1
                last_event_name = event.get("name", event.get("event", "?"))
                collected_events.append(event)
                if len(collected_events) >= _EVENT_BUFFER_SOFT_CAP:
                    await asyncio.sleep(0)
            logger.info(
                "SSE adapter: astream_events 正常结束, session_id=%s, events=%d, last=%s",
                session_id, event_count, last_event_name,
            )
        except Exception as e:
            stream_error = e
            logger.error(
                "SSE adapter: astream_events 异常 (after %d events, last=%s): %s, session_id=%s",
                event_count, last_event_name, e, session_id,
            )
        finally:
            stream_done = True
            stream_done_event.set()  # 通知主循环：流已结束

    task = asyncio.create_task(_consume_stream())
    interrupt_emitted = False
    stall_count = 0
    consecutive_failures = 0  # 连续 checkpoint 查询失败计数
    stall_start_time: Optional[float] = None  # 停滞开始时间，用于超时兜底

    try:
        while True:
            # 从 collected_events 取事件处理（每次最多 50 个，防止无限循环）
            processed = 0
            while collected_events and processed < 50:
                event = collected_events.pop(0)
                processed += 1
                kind = event.get("event", "")
                stall_count = 0  # 收到事件，重置停滞计数
                stall_start_time = None  # 收到事件，重置停滞计时

                if interrupt_emitted:
                    continue

                if kind == "on_chain_start":
                    node_name = event.get("name", "")
                    friendly = _node_friendly_name(node_name)
                    if friendly is None:
                        # 内部路由/条件节点，不向前端发送 thinking 事件
                        continue
                    yield _sse_encode({
                        "event": "thinking",
                        "data": {"message": f"正在{friendly}..."},
                    })

                elif kind == "on_chain_end":
                    node_name = event.get("name", "")
                    output = event.get("data", {}).get("output", {})
                    interrupt_value = _extract_interrupt(output) if isinstance(output, dict) else None
                    if interrupt_value:
                        logger.info(
                            "SSE adapter: interrupt from event, node=%s, type=%s",
                            node_name, interrupt_value.get("type", "unknown"),
                        )
                        yield _sse_encode({"event": "interrupt", "data": interrupt_value})
                        yield _sse_encode({
                            "event": "done",
                            "data": {"session_id": session_id, "interrupted": True},
                        })
                        interrupt_emitted = True

                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield _sse_encode({
                            "event": "text",
                            "data": {"content": chunk.content},
                        })

                elif kind == "on_custom_event" and event.get("name") == "text_chunk":
                    content = event.get("data", {}).get("content", "")
                    if content:
                        yield _sse_encode({
                            "event": "text",
                            "data": {"content": content},
                        })

            if interrupt_emitted:
                break

            # 检查生成器异常退出
            if stream_error:
                logger.error("SSE adapter: stream error: %s", stream_error)
                yield _sse_encode({
                    "event": "error",
                    "data": {"message": f"对话出错: {stream_error}"},
                })
                break

            # 检查生成器正常结束
            if stream_done and not collected_events:
                logger.info("SSE adapter: 流结束, 准备发送 done, session_id=%s", session_id)
                break

            # 等待新事件或流结束。用 asyncio.Event 通知 + 超时退避结合：
            # - 流结束时 stream_done_event 立即唤醒，不发 done 延迟
            # - 超时用于轮询 checkpoint 检测 interrupt
            if stall_count >= 2:
                sleep_interval = min(0.5 * (2 ** (stall_count - 2)), 5.0)
            else:
                sleep_interval = 0.5
            try:
                await asyncio.wait_for(stream_done_event.wait(), timeout=sleep_interval)
            except asyncio.TimeoutError:
                pass

            # 无新事件时，轮询检查点检测 interrupt（子图 interrupt 阻塞生成器）
            if not collected_events and not stream_done and graph and config:
                stall_count += 1
                # 停滞超时兜底：astream_events 可能卡在 checkpoint 写入等场景，
                # 导致 stream_done 永远不置 True，前端永远转圈。
                # 连续 30s 无新事件 → 强制 break，让前端收到 done 事件。
                now = time.monotonic()
                if stall_start_time is None:
                    stall_start_time = now
                elif now - stall_start_time >= 30:
                    logger.warning(
                        "SSE adapter: 连续停滞 %.0fs 超时, 强制发 done, session_id=%s",
                        now - stall_start_time, session_id,
                    )
                    break
                if stall_count >= 2:  # 停滞后开始检查
                    try:
                        state = await graph.aget_state(config)
                        consecutive_failures = 0  # 成功查询，重置失败计数
                        interrupts = getattr(state, 'interrupts', None) or []
                        logger.debug(
                            "SSE adapter: checkpoint poll stall=%d next=%s interrupts_count=%d",
                            stall_count, state.next, len(interrupts),
                        )
                        if state.next and interrupts:
                            interrupt_data = _interrupt_from_list(interrupts)
                            if interrupt_data:
                                logger.info(
                                    "SSE adapter: interrupt from checkpoint, "
                                    "next=%s, type=%s",
                                    state.next, interrupt_data.get("type", "unknown"),
                                )
                                yield _sse_encode({"event": "interrupt", "data": interrupt_data})
                                yield _sse_encode({
                                    "event": "done",
                                    "data": {"session_id": session_id, "interrupted": True},
                                })
                                interrupt_emitted = True
                                break
                    except Exception as e:
                        consecutive_failures += 1
                        logger.warning(
                            "SSE adapter: checkpoint check failed (%d/5): %s",
                            consecutive_failures, e,
                        )
                        if consecutive_failures >= 5:
                            logger.error("SSE adapter: checkpoint 连续失败，退出")
                            yield _sse_encode({
                                "event": "error",
                                "data": {"message": "对话出错: checkpoint 服务不可用"},
                            })
                            break
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    # 流结束后兜底：检查是否遗漏了 interrupt（生成器正常结束但子图有 interrupt）
    if not interrupt_emitted and graph and config:
        try:
            state = await graph.aget_state(config)
            interrupts = getattr(state, 'interrupts', None) or []
            if state.next and interrupts:
                interrupt_data = _interrupt_from_list(interrupts)
                if interrupt_data:
                    logger.info(
                        "SSE adapter: interrupt from post-stream checkpoint, type=%s",
                        interrupt_data.get("type", "unknown"),
                    )
                    yield _sse_encode({"event": "interrupt", "data": interrupt_data})
                    yield _sse_encode({
                        "event": "done",
                        "data": {"session_id": session_id, "interrupted": True},
                    })
                    interrupt_emitted = True
        except Exception:
            pass

    # 正常完成
    if not interrupt_emitted:
        logger.info("SSE adapter: 发送 done 事件, session_id=%s", session_id)
        yield _sse_encode({
            "event": "done",
            "data": {"session_id": session_id, "interrupted": False},
        })


def _sse_encode(event: dict) -> str:
    """编码 SSE 消息"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# 需要向用户展示的有业务意义的节点 → 友好名称
_NODE_FRIENDLY = {
    "intake_node": "分析请求",
    "analyze_file_node": "分析文件内容",
    "show_preview_node": "准备合同预览",
    "wait_user_confirm_node": "等待确认",
    "search_customer_node": "搜索客户",
    "create_customer_node": "创建客户",
    "create_contract_node": "创建合同",
    "auto_create_payments_node": "创建付款记录",
    "summarize_node": "生成总结",
    "summarize_cancel_node": "取消录入",
    "fallback_node": "处理异常",
    "call_model_node": "思考中",
    "general_chat_subgraph": "通用对话",
    "execute_tool_node": "执行操作",
    "analyze_receipt_node": "分析凭证内容",
    "receipt_entry_subgraph": "凭证录入",
    "receipt_entry_node": "处理凭证请求",
    "group_chat_node": "处理群聊请求",
    "contract_entry_subgraph": "合同录入",
}

# LangGraph 内部节点：路由/条件判断/子图包装器，不应暴露给用户
# 这些节点在 on_chain_start 时会被跳过，不发送 thinking SSE 事件
_INTERNAL_NODES = frozenset({
    "LangGraph",
    "StateGraph",
    "route_by_intent",
    "should_continue",
    "route_after_analyze",
    "route_after_execute",
    "finalize_node",
})


def _node_friendly_name(node_name: str) -> Optional[str]:
    """返回节点的用户友好名称；内部节点返回 None 表示应跳过；未映射节点显示'处理中'。"""
    if node_name in _INTERNAL_NODES:
        return None
    return _NODE_FRIENDLY.get(node_name, "处理中")


def _interrupt_from_list(interrupts: list) -> Optional[dict]:
    """从 Interrupt 列表中提取第一个 interrupt 的 value。

    用于 graph.aget_state(config).interrupts 返回的 [Interrupt, ...] 列表。
    注意：不要用 Interrupt.id（LangGraph 内部 UUID）覆盖 value 中的 interrupt_id。
    前后端校验都依赖 execute_tool_node 里生成的 contract_xxx / receipt_xxx；
    LangGraph 内部 UUID 仅用于日志追溯，作为独立字段 lg_interrupt_id 附带。
    """
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, 'value', None)
    lg_id = getattr(first, 'id', None)
    if value is None and isinstance(first, dict):
        value = first.get('value')
        lg_id = lg_id or first.get('id')
    if not isinstance(value, dict):
        return None
    result = dict(value)
    if lg_id and 'lg_interrupt_id' not in result:
        result['lg_interrupt_id'] = lg_id
    return result


def _extract_interrupt(output: dict) -> Optional[dict]:
    """从 on_chain_end 事件的 output 中提取 interrupt payload。

    LangGraph 1.2+ 使用 __interrupt__ 键名，值为 [Interrupt, ...] 列表。
    委托 _interrupt_from_list 统一处理 Interrupt 对象解析和 ID 透传。
    """
    interrupts = output.get("__interrupt__")
    if not interrupts or not isinstance(interrupts, list):
        return None
    return _interrupt_from_list(interrupts)
