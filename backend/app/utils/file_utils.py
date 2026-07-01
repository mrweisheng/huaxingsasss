"""
文件工具函数

路径解析与哈希计算的工具集合。文件写入/校验相关辅助函数已移除（孤儿）。
"""
import os
import hashlib


def calculate_file_hash(file_content: bytes) -> str:
    """计算文件SHA256哈希"""
    return hashlib.sha256(file_content).hexdigest()


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
        os.path.join(settings.AGENT_FILE_DIR, str(user_id)),  # 新：持久化目录优先
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
