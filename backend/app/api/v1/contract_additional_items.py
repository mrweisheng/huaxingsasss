"""
合同附加项管理 API 路由

挂在 /api/v1/contracts 前缀下（与合同路由共享前缀）：
  GET    /{contract_id}/additional-items   列出附加项（所有角色可见）
  POST   /{contract_id}/additional-items   新增附加项（admin/income）
  PUT    /additional-items/{item_id}       更新附加项（admin/income）
  DELETE /additional-items/{item_id}       删除附加项（admin/income，软删）
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.core.permissions import Role
from app.models.user import User
from app.schemas.contract_additional_item import (
    AdditionalItemCreate,
    AdditionalItemUpdate,
    AdditionalItemResponse,
)
from app.services.contract_additional_item_service import AdditionalItemService

logger = logging.getLogger(__name__)

router = APIRouter()


def _assert_can_edit(current_user: User) -> None:
    """附加项与合同录入同源：expense 无权写，admin/income 可写。"""
    if current_user.role == Role.EXPENSE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="expense角色无权操作合同附加项",
        )


@router.get("/{contract_id}/additional-items", response_model=List[AdditionalItemResponse])
def list_additional_items(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出合同所有附加项（仅展示，对所有角色可见）"""
    return AdditionalItemService.list_by_contract(db, contract_id)


@router.post("/{contract_id}/additional-items", response_model=AdditionalItemResponse)
def create_additional_item(
    contract_id: int,
    item_data: AdditionalItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新增附加项"""
    _assert_can_edit(current_user)
    # 路径 contract_id 与 body 一致性校验
    if item_data.contract_id != contract_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="合同ID不一致",
        )
    try:
        return AdditionalItemService.create(db, item_data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/additional-items/{item_id}", response_model=AdditionalItemResponse)
def update_additional_item(
    item_id: int,
    item_data: AdditionalItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新附加项"""
    _assert_can_edit(current_user)
    updated = AdditionalItemService.update(db, item_id, item_data, user_id=current_user.id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附加项不存在")
    return updated


@router.delete("/additional-items/{item_id}")
def delete_additional_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除附加项（软删，引用付款的标签自动置空）"""
    _assert_can_edit(current_user)
    success = AdditionalItemService.delete(db, item_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附加项不存在")
    return {"message": "删除成功"}
