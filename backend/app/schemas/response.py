"""
统一响应格式
"""
from typing import Optional, Any, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime, timezone

T = TypeVar('T')


class ResponseModel(BaseModel, Generic[T]):
    """统一响应模型"""
    
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="消息")
    data: Optional[T] = Field(default=None, description="数据")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="时间戳")


class PaginationModel(BaseModel):
    """分页信息"""
    
    page: int = Field(..., description="当前页码")
    per_page: int = Field(..., description="每页数量")
    total: int = Field(..., description="总记录数")
    total_pages: int = Field(..., description="总页数")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    
    items: list[T] = Field(..., description="数据列表")
    pagination: PaginationModel = Field(..., description="分页信息")
