"""
文件管理API路由
"""
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.file import File
from app.api.dependencies import get_current_user
from app.models.user import User
from app.config import settings
from app.services.audit_service import AuditService

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_BASE_DIRS = {
    "contract": settings.CONTRACT_UPLOAD_DIR,
    "receipt": settings.RECEIPT_UPLOAD_DIR,
    "screenshot": settings.SCREENSHOT_UPLOAD_DIR,
}


@router.get("/{file_id}/download")
def download_file(file_id: int):
    """下载文件 - TODO"""
    return {"message": f"TODO: 下载文件 {file_id}"}


@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除文件记录及物理文件"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可删除文件"
        )

    file_record = db.query(File).filter(
        File.id == file_id,
        File.is_deleted == False,
    ).first()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )

    # 删除物理文件
    base_dir = UPLOAD_BASE_DIRS.get(file_record.related_type, settings.UPLOAD_DIR)
    physical_path = Path(base_dir) / file_record.file_path
    if physical_path.exists():
        physical_path.unlink()

    file_record.soft_delete()
    db.commit()

    AuditService.log(
        db,
        user_id=current_user.id,
        action="delete",
        entity_type="file",
        entity_id=file_id,
        old_values={
            "original_filename": file_record.original_filename,
            "related_type": file_record.related_type,
            "related_id": file_record.related_id,
        },
    )

    logger.info("文件已删除: id=%d, name=%s", file_id, file_record.original_filename)
    return {"message": "删除成功"}
