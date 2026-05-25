"""
用户模型
"""
from sqlalchemy import Column, String, Boolean, DateTime
from app.models.base import BaseModel


class User(BaseModel):
    """用户表"""
    
    __tablename__ = "users"
    
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    email = Column(String(100), unique=True, index=True, comment="邮箱")
    full_name = Column(String(100), comment="真实姓名")
    role = Column(String(20), nullable=False, default="sales", comment="角色: admin/sales/viewer/finance", index=True)
    department = Column(String(50), comment="部门")
    is_active = Column(Boolean, default=True, comment="是否激活")
    last_login_at = Column(DateTime(timezone=True), comment="最后登录时间")
