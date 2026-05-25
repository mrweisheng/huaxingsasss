"""
安全模块：JWT认证、密码加密
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT配置
ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌（Access Token）
    
    Args:
        subject: 用户ID或其他标识
        expires_delta: 过期时间增量
        
    Returns:
        JWT token字符串
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str | Any) -> str:
    """
    创建刷新令牌（Refresh Token）
    
    Args:
        subject: 用户ID
        
    Returns:
        Refresh token字符串
    """
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码
        
    Returns:
        是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    生成密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    return pwd_context.hash(password)


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码访问令牌
    
    Args:
        token: JWT token
        
    Returns:
        解码后的payload，失败返回None
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[dict]:
    """
    解码刷新令牌
    
    Args:
        token: Refresh token
        
    Returns:
        解码后的payload，失败返回None
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        # 验证token类型
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None
