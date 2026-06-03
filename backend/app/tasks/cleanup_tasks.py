"""
定时清理任务 — 清理临时上传目录中过期文件 + 过期聊天会话
"""
import os
import time
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import func

from app.tasks.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task
def cleanup_temp_files(max_age_hours: int = 24):
    """
    清理 TEMP_UPLOAD_DIR 中超过 max_age_hours 的文件。
    默认保留 24 小时。
    支持 2026/06 重构后的用户子目录结构：TEMP_UPLOAD_DIR/{user_id}/{file_id}。
    """
    temp_dir = settings.TEMP_UPLOAD_DIR
    if not os.path.exists(temp_dir):
        return {"deleted": 0, "errors": 0}

    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    deleted = 0
    errors = 0

    for root, _dirs, files in os.walk(temp_dir):
        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                if os.path.getmtime(filepath) < cutoff:
                    os.remove(filepath)
                    deleted += 1
            except Exception as e:
                logger.warning("清理临时文件失败: %s, 错误: %s", filepath, e)
                errors += 1

    # 清理空的子目录
    for root, dirs, _files in os.walk(temp_dir, topdown=False):
        for d in dirs:
            sub = os.path.join(root, d)
            try:
                if not os.listdir(sub):
                    os.rmdir(sub)
            except Exception:
                pass

    logger.info("临时文件清理完成: 删除 %d 个, 失败 %d 个", deleted, errors)
    return {"deleted": deleted, "errors": errors}


@celery_app.task
def cleanup_old_chat_sessions(max_age_days: int = 90):
    """
    清理超过 max_age_days 无活动的聊天会话及其关联 Redis 缓存。
    默认保留 90 天。
    """
    from app.db.session import SessionLocal
    from app.models.chat_history import ChatHistory
    import redis as redis_lib

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)

        # 找出最新消息早于 cutoff 的会话
        old_sessions = (
            db.query(ChatHistory.session_id)
            .group_by(ChatHistory.session_id)
            .having(func.max(ChatHistory.created_at) < cutoff)
            .all()
        )

        if not old_sessions:
            return {"deleted_sessions": 0, "deleted_messages": 0}

        # 初始化 Redis（可选，失败不影响 DB 清理）
        redis_client = None
        try:
            redis_client = redis_lib.Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2,
                decode_responses=True,
            )
            redis_client.ping()
        except Exception:
            logger.debug("Redis 不可用，跳过缓存清理")

        deleted_sessions = 0
        deleted_messages = 0
        for (session_id,) in old_sessions:
            count = db.query(ChatHistory).filter(
                ChatHistory.session_id == session_id
            ).delete()
            deleted_messages += count
            deleted_sessions += 1

            # 清理该会话的 Redis 缓存
            if redis_client:
                try:
                    _cleanup_session_redis(redis_client, session_id)
                except Exception:
                    pass

        db.commit()
        logger.info(
            "聊天历史清理完成: %d 个会话, %d 条消息",
            deleted_sessions, deleted_messages,
        )
        return {
            "deleted_sessions": deleted_sessions,
            "deleted_messages": deleted_messages,
        }
    finally:
        db.close()


def _cleanup_session_redis(redis_client, session_id: str) -> None:
    """清理单个会话的 Redis 缓存（VL 分析缓存 + 摘要缓存）"""
    # 清理 VL 分析缓存: vl:*:{session_id}:*
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(
            cursor, match=f"vl:*:{session_id}:*", count=100,
        )
        if keys:
            redis_client.delete(*keys)
        if cursor == 0:
            break
    # 清理摘要缓存
    redis_client.delete(f"agent_summary:{session_id}")
