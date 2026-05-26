"""
文件工具函数
"""
import os
import uuid
import hashlib
from pathlib import Path
from datetime import datetime
from fastapi import UploadFile


def generate_unique_filename(original_filename: str, prefix: str = "") -> str:
    """生成唯一文件名"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    ext = original_filename.split('.')[-1] if '.' in original_filename else 'bin'
    
    filename = f"{prefix}{timestamp}_{unique_id}.{ext}"
    return filename


def calculate_file_hash(file_content: bytes) -> str:
    """计算文件SHA256哈希"""
    return hashlib.sha256(file_content).hexdigest()


async def save_uploaded_file(
    file: UploadFile,
    base_dir: str,
    sub_dir: str = ""
) -> tuple[str, str, int]:
    """
    保存上传文件
    
    Returns:
        (relative_path, file_hash, file_size)
    """
    # 创建目录
    year_month = datetime.now().strftime("%Y/%m")
    target_dir = Path(base_dir) / sub_dir / year_month
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 读取文件内容
    content = await file.read()
    file_size = len(content)
    
    # 生成文件名并保存
    filename = generate_unique_filename(file.filename)
    file_path = target_dir / filename
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # 计算哈希
    file_hash = calculate_file_hash(content)
    
    # 返回相对路径
    relative_path = str(Path(sub_dir) / year_month / filename)
    
    return relative_path, file_hash, file_size


# 文件魔数字节映射（支持扩展名变体）
MAGIC_BYTES = {
    b'\xff\xd8\xff': ('jpeg', 'jpg'),
    b'\x89PNG\r\n\x1a\n': ('png',),
    b'%PDF': ('pdf',),
}


def validate_file_magic(content: bytes, allowed_extensions: list[str]) -> bool:
    """通过文件魔数字节验证文件真实类型"""
    for magic, exts in MAGIC_BYTES.items():
        if content.startswith(magic):
            return any(ext in allowed_extensions for ext in exts)
    return False


def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return filename.split('.')[-1].lower() if '.' in filename else ''


def validate_file_type(filename: str, allowed_types: list[str]) -> bool:
    """验证文件类型"""
    ext = get_file_extension(filename)
    return ext in allowed_types
