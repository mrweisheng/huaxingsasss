"""
认证API路由
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_refresh_token
)
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, TokenResponse, UserResponse
from app.api.dependencies import get_current_user

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    admin_token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    用户注册
    - 不传 admin_token: 默认注册为 sales 角色（普通业务员）
    - 传 admin_token: 管理员可为用户指定任意角色
    """
    from app.core.security import decode_access_token

    # 确定角色：非管理员只能创建 sales 用户
    role = "sales"
    if admin_token:
        payload = decode_access_token(admin_token)
        if payload:
            admin_user = db.query(User).filter(User.id == int(payload.get("sub", 0))).first()
            if admin_user and admin_user.role == "admin" and admin_user.is_active:
                role = user_data.role  # 管理员可指定角色

    # 检查用户名是否已存在
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在"
        )

    # 检查邮箱是否已存在
    if user_data.email and db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已被使用"
        )

    # 创建新用户
    user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=get_password_hash(user_data.password),
        role=role,
        department=user_data.department,
        is_active=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
# TODO: 添加登录速率限制（如 slowapi 或自定义中间件）
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    # 查找用户
    user = db.query(User).filter(User.username == login_data.username).first()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    # 生成token
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    # 更新最后登录时间
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,
        user=UserResponse.from_orm(user)
    )


@router.post("/refresh", response_model=dict)
def refresh_token(refresh_token: str = Body(..., embed=True), db: Session = Depends(get_db)):
    """刷新访问令牌"""
    payload = decode_refresh_token(refresh_token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    new_access_token = create_access_token(subject=user.id)
    
    return {
        "access_token": new_access_token,
        "expires_in": 3600
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user
