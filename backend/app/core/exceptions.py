"""
自定义异常类
"""
from typing import Optional, Any


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


class AuthenticationError(AppException):
    """认证错误"""
    
    def __init__(self, message: str = "认证失败，请重新登录"):
        super().__init__(message=message, code=401)


class AuthorizationError(AppException):
    """授权错误（权限不足）"""
    
    def __init__(self, message: str = "权限不足，无法执行此操作"):
        super().__init__(message=message, code=403)


class NotFoundError(AppException):
    """资源不存在"""
    
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message=message, code=404)


class ValidationError(AppException):
    """数据验证错误"""
    
    def __init__(self, message: str = "数据验证失败", details: Optional[dict] = None):
        super().__init__(message=message, code=400, details=details)


class DuplicateError(AppException):
    """重复数据错误"""
    
    def __init__(self, message: str = "数据已存在"):
        super().__init__(message=message, code=409)


class FileUploadError(AppException):
    """文件上传错误"""
    
    def __init__(self, message: str = "文件上传失败"):
        super().__init__(message=message, code=500)


class AIProcessingError(AppException):
    """AI处理错误"""

    def __init__(self, message: str = "AI处理失败"):
        super().__init__(message=message, code=500)


def raise_not_found(message: str = "资源不存在"):
    """快捷抛出 NotFoundError"""
    raise NotFoundError(message)


def raise_forbidden(message: str = "权限不足，无法执行此操作"):
    """快捷抛出 AuthorizationError"""
    raise AuthorizationError(message)
