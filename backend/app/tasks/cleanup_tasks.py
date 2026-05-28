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
    """
    temp_dir = settings.TEMP_UPLOAD_DIR
    if not os.path.exists(temp_dir):
        return {"deleted": 0, "errors": 0}

    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    deleted = 0
    errors = 0

    for filename in os.listdir(temp_dir):
        filepath = os.path.join(temp_dir, filename)
        if os.path.isfile(filepath):
            try:
                if os.path.getmtime(filepath) < cutoff:
                    os.remove(filepath)
                    deleted += 1
            except Exception as e:
                logger.warning("清理临时文件失败: %s, 错误: %s", filepath, e)
                errors += 1

    logger.info("临时文件清理完成: 删除 %d 个, 失败 %d 个", deleted, errors)
    return {"deleted": deleted, "errors": errors}
