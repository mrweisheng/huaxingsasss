"""LangGraph PostgresSaver 异步检查点工厂

ADR #5：直接用 AsyncPostgresSaver + psycopg3 连接池，复用现有 PostgreSQL。
不分三阶段（InMemory → Sqlite → Postgres）演进。

用法：
    # FastAPI startup
    await init_checkpointer()

    # 节点 / Graph 编译
    cp = get_checkpointer()
    app = graph.compile(checkpointer=cp)

    # FastAPI shutdown
    await close_checkpointer()
"""
import logging
from typing import Optional

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None


async def init_checkpointer(max_pool_size: int = 20) -> AsyncPostgresSaver:
    """初始化全局 checkpointer + 连接池。

    首次运行会自动创建 checkpoints / checkpoint_writes / checkpoint_blobs
    三张表。表已存在时 setup() 为 no-op。

    再次调用时直接返回已存在的实例（幂等）。
    """
    global _pool, _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    # psycopg3 需要的 kwargs：
    #   autocommit=True  — LangGraph PostgresSaver 内部管理事务
    #   prepare_threshold=0 — 关闭 prepared statement，兼容某些 PG 代理
    _pool = AsyncConnectionPool(
        conninfo=settings.DATABASE_URL,
        max_size=max_pool_size,
        open=False,  # 必须 False，由 await pool.open() 异步打开
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    await _pool.open()

    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()

    logger.info(
        "langgraph_checkpointer_initialized: db=%s host=%s pool_max=%d",
        settings.POSTGRES_DB,
        settings.POSTGRES_SERVER,
        max_pool_size,
    )
    return _checkpointer


async def close_checkpointer() -> None:
    """关闭连接池。FastAPI shutdown 调用。"""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        logger.info("langgraph_checkpointer_closed")
    _pool = None
    _checkpointer = None


def get_checkpointer() -> AsyncPostgresSaver:
    """获取已初始化的 checkpointer。

    在 init_checkpointer() 之前调用会抛 RuntimeError。
    """
    if _checkpointer is None:
        raise RuntimeError(
            "checkpointer 未初始化。请确认 FastAPI startup 钩子已调用 "
            "app.ai.orchestrator.checkpointer.init_checkpointer()。"
        )
    return _checkpointer
