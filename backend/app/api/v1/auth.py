"""
认证API路由
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from sqlalchemy.orm import Session
import structlog

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
from app.utils.rate_limiter import login_rate_limiter

logger = structlog.get_logger()

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    admin_token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    用户注册
    - 不传 admin_token: 默认注册为 income 角色（收入专员）
    - 传 admin_token: 管理员可为用户指定任意角色
    """
    from app.core.security import decode_access_token

    # 确定角色：非管理员只能创建 income 用户
    role = "income"
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
async def login(request: Request, login_data: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    logger.info("login_attempt", username=login_data.username, client_ip=client_ip)

    # 速率限制（基于客户端IP）
    try:
        await login_rate_limiter.check(f"login:{client_ip}")
    except HTTPException:
        logger.warning("login_rate_limited", username=login_data.username, client_ip=client_ip)
        raise

    # 查找用户
    logger.debug("login_query_user", username=login_data.username)
    try:
        user = db.query(User).filter(User.username == login_data.username).first()
    except Exception as e:
        logger.error("login_db_query_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="数据库查询失败，请检查数据库连接"
        )

    if not user:
        logger.warning("login_user_not_found", username=login_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证密码
    logger.debug("login_verify_password", username=login_data.username)
    try:
        password_valid = verify_password(login_data.password, user.password_hash)
    except ValueError as e:
        logger.error("login_password_verify_value_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码验证服务异常（密码格式错误）"
        )
    except Exception as e:
        logger.error("login_password_verify_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码验证服务异常"
        )

    if not password_valid:
        logger.warning("login_wrong_password", username=login_data.username, user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning("login_user_disabled", username=login_data.username, user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )

    # 生成token
    logger.debug("login_generating_tokens", username=login_data.username, user_id=user.id)
    try:
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)
    except Exception as e:
        logger.error("login_token_generation_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="令牌生成失败"
        )

    # 更新最后登录时间
    try:
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        logger.warning("login_update_last_login_failed", error=str(e), exc_info=True)
        db.rollback()

    logger.info("login_success", username=login_data.username, user_id=user.id, role=user.role)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,
        user=UserResponse.model_validate(user)
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
