"""
自定义异常类
"""
from typing import Optional


class AppException(Exception):
    """应用基础异常类"""

    def __init__(
        self,
        message: str = "操作失败",
        code: int = 400,
        details: Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.details = details
        super().__init__(self.message)
