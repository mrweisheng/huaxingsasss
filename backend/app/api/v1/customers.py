"""
客户管理API路由
"""
from typing import Optional, List
import base64
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.session import get_db
from app.core.chinese import search_variants
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse
from app.schemas.response import ResponseModel, PaginatedResponse, PaginationModel
from app.api.dependencies import get_current_user, require_role
from app.core.permissions import Role, is_admin, can_view_income
from app.models.user import User
from app.services.customer_service import CustomerService

router = APIRouter()


def escape_ilike(text: str) -> str:
    """转义 ILIKE 查询中的特殊字符 % 和 _"""
    return text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


@router.get("", response_model=PaginatedResponse[CustomerResponse])
def list_customers(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取客户列表"""
    query = db.query(Customer).filter(Customer.is_deleted == False)

    # admin/income 可查看全部，expense 不可查看客户
    if current_user.role == Role.EXPENSE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色无权查看客户")
    if current_user.role == Role.INCOME:
        query = query.filter(Customer.created_by == current_user.id)
    
    # 关键词搜索
    if keyword:
        variants = search_variants(keyword)
        escaped = [escape_ilike(v) for v in variants]
        name_filters = [Customer.name.ilike(f"%{v}%") for v in escaped]
        wechat_filters = [Customer.wechat_group_name.ilike(f"%{v}%") for v in escaped]
        query = query.filter(
            or_(
                *name_filters,
                Customer.phone.ilike(f"%{escape_ilike(keyword)}%"),
                Customer.email.ilike(f"%{escape_ilike(keyword)}%"),
                *wechat_filters,
            )
        )
    
    # 总数
    total = query.count()
    
    # 分页
    items = query.order_by(Customer.created_at.desc())\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()
    
    return PaginatedResponse(
        items=[CustomerResponse.model_validate(item) for item in items],
        pagination=PaginationModel(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page
        )
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer_data: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建客户"""
    # expense 角色不可创建客户
    if current_user.role == Role.EXPENSE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色无权创建客户")
    # 校验：至少提供电话或邮箱
    if not customer_data.phone and not customer_data.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="电话和邮箱至少填写一项"
        )

    # 检查是否已存在（同名+同电话 或 同名+同邮箱，排除已删除）
    existing = None
    if customer_data.phone:
        existing = db.query(Customer).filter(
            Customer.name == customer_data.name,
            Customer.phone == customer_data.phone,
            Customer.is_deleted == False,
        ).first()
    if not existing and customer_data.email:
        existing = db.query(Customer).filter(
            Customer.name == customer_data.name,
            Customer.email == customer_data.email,
            Customer.is_deleted == False,
        ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="客户已存在（同名且电话/邮箱相同）"
        )

    # 创建客户
    customer = Customer(
        name=customer_data.name,
        contact_person=customer_data.contact_person,
        phone=customer_data.phone,
        email=customer_data.email,
        id_card_number_encrypted=base64.b64encode(customer_data.id_card_number.encode()).decode() if customer_data.id_card_number else None,
        business_license=customer_data.business_license,
        address=customer_data.address,
        wechat_group_name=customer_data.wechat_group_name,
        remarks=customer_data.remarks,
        created_by=current_user.id
    )
    
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    return customer


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取客户详情"""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_deleted == False,
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="客户不存在"
        )
    
    # 权限检查
    if current_user.role == Role.EXPENSE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色无权查看客户")
    if current_user.role == Role.INCOME and customer.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此客户"
        )

    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新客户"""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_deleted == False,
    ).first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="客户不存在"
        )

    # 权限检查
    if current_user.role == Role.EXPENSE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色无权修改客户")
    if current_user.role == Role.INCOME and customer.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此客户"
        )
    
    # 更新字段（处理加密字段映射）
    update_data = customer_data.model_dump(exclude_unset=True)

    # 特殊处理：id_card_number → id_card_number_encrypted
    if 'id_card_number' in update_data:
        id_card = update_data.pop('id_card_number')
        # TODO: 生产环境应使用 Fernet 对称加密（cryptography.fernet）
        customer.id_card_number_encrypted = base64.b64encode(id_card.encode()).decode() if id_card else None

    for field, value in update_data.items():
        setattr(customer, field, value)
    
    db.commit()
    db.refresh(customer)
    
    return customer


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除客户（软删除）"""
    # 权限检查（仅管理员可删除）
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可删除客户"
        )

    try:
        success = CustomerService.delete_customer(db, customer_id, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="客户不存在"
        )

    return {"message": "删除成功"}
