"""
客户管理API路由

CLAUDE.md 硬规则：路由层不操作 ORM，所有 DB 访问下沉到 CustomerService。
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.customer import CustomerUpdate, CustomerResponse
from app.schemas.response import PaginatedResponse, PaginationModel
from app.api.dependencies import get_current_user
from app.core.permissions import Role, is_admin
from app.models.user import User
from app.services.customer_service import CustomerService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[CustomerResponse])
def list_customers(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取客户列表（客户对所有角色全部可见）"""
    items, total = CustomerService.get_list(db, page=page, per_page=per_page, keyword=keyword)

    return PaginatedResponse(
        items=[CustomerResponse.model_validate(item) for item in items],
        pagination=PaginationModel(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page,
        ),
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取客户详情（客户详情对所有角色可见）"""
    customer = CustomerService.get_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户不存在")
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新客户（income 可改任意客户，expense 不可修改）"""
    if current_user.role == Role.EXPENSE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色无权修改客户")

    customer = CustomerService.update(db, customer_id, customer_data, updated_by=current_user.id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户不存在")
    return customer


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除客户（软删除，仅管理员）"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可删除客户")

    try:
        success = CustomerService.delete_customer(db, customer_id, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户不存在")

    return {"message": "删除成功"}
