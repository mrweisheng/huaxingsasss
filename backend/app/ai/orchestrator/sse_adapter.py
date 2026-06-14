"""LangGraph astream_events -> SSE 事件格式适配器 v2.3

适配统一 Agent 图（call_model_node / execute_tool_node / finalize_node）。

SSE 事件输出：
  - thinking    — 节点启动提示 + 工具执行期心跳
  - text        — LLM 流式输出 / text_chunk 自定义事件
  - tool_call   — 工具调用开始（tool_start 自定义事件）
  - tool_result — 工具调用结束（tool_end 自定义事件，含 summary）
  - done        — 流结束
  - error       — 异常

v2.3 修复：用 asyncio.wait 替代 asyncio.wait_for 实现心跳。
wait_for 在超时时会取消底层 async generator 的 __anext__()，
导致工具执行超过 3 秒时生成器被关闭、SSE 流提前结束。
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

# 心跳间隔（秒）：当两个事件之间间隔超过此值，自动发 thinking 心跳
_HEARTBEAT_INTERVAL = 3.0

# 心跳文案池（复用前端 WittyLoadingText 的关键词触发场景）
_HEARTBEAT_MESSAGES = [
    "正在处理中...",
    "还在努力干活...",
    "数据量有点大，稍等一下...",
    "快好了，再给我一点时间...",
    "正在核对信息...",
]

# 哨兵值：标记 async generator 迭代结束
_STREAM_END = object()


def _sse_encode(event: dict) -> str:
    """编码 SSE 消息"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# 需要向用户展示的有业务意义的节点 → 友好名称
_NODE_FRIENDLY = {
    "call_model_node": "思考中",
    "execute_tool_node": "执行操作",
    "finalize_node": "保存记录",
}

# LangGraph 内部节点：路由/条件判断，不应暴露给用户
_INTERNAL_NODES = frozenset({
    "LangGraph",
    "StateGraph",
    "should_continue",
})


def _node_friendly_name(node_name: str) -> Optional[str]:
    """返回节点的用户友好名称；内部节点返回 None 表示应跳过；未映射节点显示'处理中'。"""
    if node_name in _INTERNAL_NODES:
        return None
    return _NODE_FRIENDLY.get(node_name, "处理中")


async def _safe_anext(aiter):
    """安全包装 aiter.__anext__()，将 StopAsyncIteration 转为哨兵值。

    这样 asyncio.create_task 不会因 StopAsyncIteration 产生意外行为。
    """
    try:
        return await aiter.__anext__()
    except StopAsyncIteration:
        return _STREAM_END


async def adapt_langgraph_stream_v2(
    agen,
    session_id: str,
) -> AsyncGenerator[str, None]:
    """将 LangGraph astream_events 流转换为 SSE 事件格式。

    适配统一 Agent 图（call_model_node / execute_tool_node / finalize_node）。
    当两个事件之间间隔超过 _HEARTBEAT_INTERVAL 秒时，自动发 thinking 心跳事件，
    防止前端因长时间无事件而看起来"卡住"。

    v2.3: 使用 asyncio.wait + Task 实现心跳，避免 wait_for 取消 async generator。
    """
    event_count = 0
    last_event_name = ""
    heartbeat_idx = 0

    aiter = agen.__aiter__()
    # 用 Task 包装 __anext__()，以便 asyncio.wait 可以只检测完成而不取消
    _next_task: Optional[asyncio.Task] = None

    try:
        while True:
            # 确保 always have a pending task for the next event
            if _next_task is None:
                _next_task = asyncio.create_task(_safe_anext(aiter))

            # asyncio.wait 不会取消未完成的 task —— 这是关键区别
            done, _ = await asyncio.wait(
                {_next_task},
                timeout=_HEARTBEAT_INTERVAL,
            )

            if not done:
                # 超时 → 发心跳（task 仍在运行，不被取消）
                heartbeat_msg = _HEARTBEAT_MESSAGES[heartbeat_idx % len(_HEARTBEAT_MESSAGES)]
                heartbeat_idx += 1
                yield _sse_encode({
                    "event": "thinking",
                    "data": {"message": heartbeat_msg},
                })
                continue

            # 事件到达 → 取结果，清理 task 引用
            _next_task = None
            event = done.pop().result()

            # 检查哨兵：生成器结束
            if event is _STREAM_END:
                break

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

            elif kind == "on_custom_event" and event.get("name") == "tool_start":
                data = event.get("data", {})
                if data.get("name"):
                    yield _sse_encode({
                        "event": "tool_call",
                        "data": {
                            "id": data.get("id", ""),
                            "name": data["name"],
                            "arguments": data.get("arguments", "{}"),
                        },
                    })

            elif kind == "on_custom_event" and event.get("name") == "tool_end":
                data = event.get("data", {})
                if data.get("name"):
                    payload: dict = {
                        "id": data.get("id", ""),
                        "name": data["name"],
                        "result": data.get("result", ""),
                    }
                    if data.get("summary") is not None:
                        payload["summary"] = data["summary"]
                    yield _sse_encode({
                        "event": "tool_result",
                        "data": payload,
                    })

        logger.info(
            "SSE adapter: astream_events 正常结束, session_id=%s, events=%d, last=%s, heartbeats=%d",
            session_id, event_count, last_event_name, heartbeat_idx,
        )
    except Exception as e:
        # 输出完整 traceback，便于定位 NameError 等异常的精确位置
        logger.exception(
            "SSE adapter: astream_events 异常 (after %d events, last=%s): %s, session_id=%s",
            event_count, last_event_name, e, session_id,
        )
        yield _sse_encode({
            "event": "error",
            "data": {"message": f"对话出错: {e}"},
        })
        return

    yield _sse_encode({
        "event": "done",
        "data": {"session_id": session_id},
    })


# 保留旧名兼容（指向 v2）
adapt_langgraph_stream = adapt_langgraph_stream_v2
