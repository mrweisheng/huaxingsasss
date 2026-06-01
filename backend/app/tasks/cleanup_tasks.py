"""
定时清理任务 — 清理临时上传目录中过期文件
"""
import os
import time
import logging

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
