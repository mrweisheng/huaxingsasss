"""
用户相关Pydantic模型
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """用户基础模型"""
    
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    full_name: Optional[str] = Field(None, max_length=100, description="真实姓名")


class UserCreate(UserBase):
    """创建用户"""
    
    password: str = Field(..., min_length=8, description="密码")
    role: str = Field(default="income", description="角色")
    department: Optional[str] = Field(None, max_length=50, description="部门")


class UserUpdate(BaseModel):
    """更新用户"""
    
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """用户响应"""

    id: int
    role: str
    department: Optional[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """用户登录"""
    
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """Token响应"""
    
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserResponse


class AdminUserCreate(BaseModel):
    """管理员创建用户（默认密码 123456）"""
    
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    full_name: str = Field(..., max_length=100, description="真实姓名")
    role: str = Field(default="income", description="角色: admin/income/expense")
    department: Optional[str] = Field(None, max_length=50, description="部门")
    email: Optional[EmailStr] = Field(None, description="邮箱")


class UserUpdateByAdmin(BaseModel):
    """管理员编辑用户"""
    
    full_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    department: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, description="角色: admin/income/expense")


class UserListResponse(BaseModel):
    """用户列表响应（含时间字段）"""

    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    role: str
    department: Optional[str]
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ChangePasswordRequest(BaseModel):
    """修改密码（已认证）"""
    
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码（至少6位）")


class PublicChangePasswordRequest(BaseModel):
    """公开修改密码（未认证，需用户名）"""
    
    username: str = Field(..., description="用户名")
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码（至少6位）")
