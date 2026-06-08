"""LangGraph astream_events -> 现有 SSE 事件格式适配器

文档 6.8：LangGraph 事件 -> SSE 事件映射表
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


async def adapt_langgraph_stream(
    agen,  # AsyncGenerator from astream_events
    session_id: str,
) -> AsyncGenerator[str, None]:
    """将 LangGraph astream_events 流转换为现有 SSE 事件格式。

    直接消费 astream_events 生成器，不引入后台任务和 checkpoint 轮询
    （已废弃 interrupt 机制，astream_events 不会阻塞）。

    Args:
        agen: graph.astream_events(initial_state, config, version="v2") 的返回
        session_id: 会话 ID

    Yields:
        "data: {json}\\n\\n" 格式的 SSE 字符串
    """
    event_count = 0
    last_event_name = ""
    stall_start_time: Optional[float] = None

    try:
        async for event in agen:
            event_count += 1
            last_event_name = event.get("name", event.get("event", "?"))
            kind = event.get("event", "")

            if kind == "on_chain_start":
                node_name = event.get("name", "")
                friendly = _node_friendly_name(node_name)
                if friendly is None:
                    continue
                yield _sse_encode({
                    "event": "thinking",
                    "data": {"message": f"正在{friendly}..."},
                })

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

            # 重置停滞计时（有事件产出）
            stall_start_time = None

        logger.info(
            "SSE adapter: astream_events 正常结束, session_id=%s, events=%d, last=%s",
            session_id, event_count, last_event_name,
        )
    except Exception as e:
        logger.error(
            "SSE adapter: astream_events 异常 (after %d events, last=%s): %s, session_id=%s",
            event_count, last_event_name, e, session_id,
        )
        yield _sse_encode({
            "event": "error",
            "data": {"message": f"对话出错: {e}"},
        })
        return

    # 正常完成
    logger.info("SSE adapter: 发送 done 事件, session_id=%s", session_id)
    yield _sse_encode({
        "event": "done",
        "data": {"session_id": session_id},
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
