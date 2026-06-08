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


def validate_file_id_in_dir(file_id: str, base_dir: str) -> str | None:
    """校验 file_id 并返回安全路径，防止路径穿越。

    file_id 应为 UUID 格式（可带扩展名如 UUID.docx），
    不允许包含 / \\ .. 等路径成分。

    Args:
        file_id: 文件 ID（UUID 或 UUID.ext）
        base_dir: 基目录

    Returns:
        安全路径字符串，或 None（file_id 非法时）
    """
    # 拒绝含路径成分的 file_id
    if "/" in file_id or "\\" in file_id or ".." in file_id:
        return None

    candidate = os.path.join(base_dir, file_id)
    resolved = os.path.realpath(candidate)
    allowed_prefix = os.path.realpath(base_dir)

    # 确保解析后路径在允许目录内
    if not resolved.startswith(allowed_prefix + os.sep) and resolved != allowed_prefix:
        return None

    return resolved


def resolve_file_path(file_id: str, user_id: int) -> str | None:
    """解析上传文件路径：优先用户隔离路径，回退全局路径。

    支持两种 file_id 格式：
      - 新版（带扩展名）：UUID.docx / UUID.pdf
      - 旧版（无扩展名）：UUID

    含路径穿越防御（委托 validate_file_id_in_dir）。
    从 app.services.contract_analyzer 抽出（PR-R-3），作为通用文件工具供
    Agent 子图、API 端点、Service 层共用，避免"合同名"的语义耦合。

    Args:
        file_id: 上传接口返回的文件 ID
        user_id: 当前用户 ID（用于优先匹配用户隔离目录）

    Returns:
        存在的文件绝对路径，或 None（未找到时）
    """
    from app.config import settings  # 延迟导入避免循环依赖

    for base_dir in (
        os.path.join(settings.TEMP_UPLOAD_DIR, str(user_id)),
        settings.TEMP_UPLOAD_DIR,
    ):
        # 精确匹配：file_id 直接作为文件名
        safe_path = validate_file_id_in_dir(file_id, base_dir)
        if safe_path and os.path.isfile(safe_path):
            return safe_path

        # 扩展名兜底：扫描同 file_id 前缀的所有文件
        if os.path.isdir(base_dir):
            for fname in sorted(os.listdir(base_dir)):
                if fname.startswith(file_id + ".") or fname == file_id:
                    candidate = os.path.join(base_dir, fname)
                    if os.path.isfile(candidate) and os.path.realpath(candidate).startswith(
                        os.path.realpath(base_dir) + os.sep
                    ):
                        return candidate
    return None
