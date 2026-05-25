"""
文件管理API路由 - TODO: Phase 3实现
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/{file_id}/download")
def download_file(file_id: int):
    """下载文件 - TODO"""
    return {"message": f"TODO: 下载文件 {file_id}"}


@router.delete("/{file_id}")
def delete_file(file_id: int):
    """删除文件 - TODO"""
    return {"message": f"TODO: 删除文件 {file_id}"}
