"""
用户管理API路由

仅 admin 角色可访问用户管理功能（列表、创建、编辑、启禁用、重置密码）。
已认证用户可修改自己的密码。
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.api.dependencies import get_current_user, require_role
from app.schemas.user import (
    AdminUserCreate,
    UserUpdateByAdmin,
    UserListResponse,
    ChangePasswordRequest,
)
from app.schemas.response import ResponseModel, PaginatedResponse, PaginationModel
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[UserListResponse])
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """用户列表（分页 + 搜索）"""
    items, total = UserService.get_users(db, page=page, per_page=per_page, keyword=keyword)
    return PaginatedResponse(
        items=[UserListResponse.model_validate(u) for u in items],
        pagination=PaginationModel(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page,
        ),
    )


@router.post("", response_model=UserListResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: AdminUserCreate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """创建用户（默认密码 123456）"""
    try:
        user = UserService.create_user(db, data, created_by=current_user.id)
        return UserListResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.put("/me/password", response_model=ResponseModel)
def change_my_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改自己的密码"""
    try:
        UserService.change_password(db, current_user.id, data.old_password, data.new_password)
        return ResponseModel(code=200, message="密码修改成功")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{user_id}", response_model=UserListResponse)
def update_user(
    user_id: int = Path(..., ge=1),
    data: UserUpdateByAdmin = ...,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """编辑用户"""
    try:
        user = UserService.update_user(db, user_id, data, updated_by=current_user.id)
        return UserListResponse.model_validate(user)
    except ValueError as e:
        detail = str(e)
        if "不存在" in detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.patch("/{user_id}/toggle-active", response_model=UserListResponse)
def toggle_user_active(
    user_id: int = Path(..., ge=1),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """启用/禁用用户"""
    try:
        user = UserService.toggle_active(db, user_id, operator_id=current_user.id)
        return UserListResponse.model_validate(user)
    except ValueError as e:
        detail = str(e)
        if "不能禁用" in detail:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.post("/{user_id}/reset-password", response_model=ResponseModel)
def reset_user_password(
    user_id: int = Path(..., ge=1),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """重置用户密码为默认密码"""
    try:
        UserService.reset_password(db, user_id, operator_id=current_user.id)
        return ResponseModel(code=200, message="密码已重置为默认密码")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
