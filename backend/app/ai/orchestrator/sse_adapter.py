"""LangGraph astream_events → 现有 SSE 事件格式适配

文档 §6.8：LangGraph 事件 → SSE 事件映射表
Phase 1 新增 interrupt 事件类型
"""
import json
import logging
from typing import AsyncGenerator

from app.ai.orchestrator.state import RootState

logger = logging.getLogger(__name__)


async def adapt_langgraph_stream(
    agen,  # AsyncGenerator from astream_events
    session_id: str,
) -> AsyncGenerator[str, None]:
    """将 LangGraph astream_events 流转换为现有 SSE 事件格式。

    Args:
        agen: graph.astream_events(initial_state, config, version="v2") 的返回
        session_id: 会话 ID

    Yields:
        "data: {json}\n\n" 格式的 SSE 字符串
    """
    interrupt_emitted = False

    async for event in agen:
        kind = event.get("event", "")

        # interrupt 已触发后：仅监听"新的 interrupt 事件"（多步流程），
        # 跳过 on_chain_start / on_chat_model_stream / on_chat_model_end 等
        # 收尾/干扰事件，避免脏数据污染确认面板。
        # 多步 interrupt 的标准实现：第一次 interrupt → 用户 resume → LangGraph
        # 在新的 astream_events 调用中 emit 第二个 interrupt；同一个 stream 内
        # 不会连续触发两个 interrupt。所以此处 `continue` 是为了理论完备性，
        # 实际单步/多步流程的行为相同。
        if interrupt_emitted:
            if kind == "on_chain_end":
                next_output = event.get("data", {}).get("output", {})
                if isinstance(next_output, dict) and next_output.get("interrupt_info"):
                    yield _sse_encode({
                        "event": "interrupt",
                        "data": next_output["interrupt_info"],
                    })
                    yield _sse_encode({
                        "event": "done",
                        "data": {"session_id": session_id, "interrupted": True},
                    })
            continue

        if kind == "on_chain_start":
            node_name = event.get("name", "")
            sse = {
                "event": "thinking",
                "data": {"message": f"正在{_node_friendly_name(node_name)}..."},
            }
            yield _sse_encode(sse)

        elif kind == "on_chain_end":
            node_name = event.get("name", "")
            output = event.get("data", {}).get("output", {})
            if isinstance(output, dict) and output.get("interrupt_info"):
                # interrupt 触发 → 推送 interrupt 事件 + done(interrupted=true)，
                # 然后进入"仅监听新 interrupt"模式
                sse_interrupt = {
                    "event": "interrupt",
                    "data": output["interrupt_info"],
                }
                yield _sse_encode(sse_interrupt)

                sse_done = {
                    "event": "done",
                    "data": {"session_id": session_id, "interrupted": True},
                }
                yield _sse_encode(sse_done)
                interrupt_emitted = True

        elif kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                sse = {
                    "event": "text",
                    "data": {"content": chunk.content},
                }
                yield _sse_encode(sse)

        elif kind == "on_chat_model_end":
            pass  # 流结束标记

    # 未触发 interrupt 的正常完成
    if not interrupt_emitted:
        sse = {
            "event": "done",
            "data": {"session_id": session_id, "interrupted": False},
        }
        yield _sse_encode(sse)


def _sse_encode(event: dict) -> str:
    """编码 SSE 消息"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


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
    "finalize_node": "保存记录",
    "general_chat_start_node": "分析中",
}


def _node_friendly_name(node_name: str) -> str:
    return _NODE_FRIENDLY.get(node_name, node_name)
