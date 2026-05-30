"""
用户相关Pydantic模型
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


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
    
    class Config:
        from_attributes = True


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
