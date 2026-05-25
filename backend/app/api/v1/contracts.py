"""
合同管理API路由
"""
from typing import Optional, List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import date

from app.db.session import get_db
from app.models.contract import Contract
from app.schemas.contract import ContractCreate, ContractUpdate, ContractResponse, ContractParseResult
from app.schemas.response import ResponseModel, PaginatedResponse, PaginationModel
from app.api.dependencies import get_current_user, require_role
from app.models.user import User
from app.services.contract_service import ContractService
from app.utils.file_utils import save_uploaded_file, calculate_file_hash
from app.config import settings

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ContractResponse])
def list_contracts(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="合同状态"),
    customer_id: Optional[int] = Query(None, description="客户ID"),
    customer_name: Optional[str] = Query(None, description="客户名称"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    date_from: Optional[date] = Query(None, description="签订日期起始"),
    date_to: Optional[date] = Query(None, description="签订日期结束"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同列表"""
    # 管理员和财务可查看全部，其他角色只看自己负责的
    sales_person_id = None if current_user.role in ("admin", "finance") else current_user.id
    
    items, total = ContractService.get_contracts(
        db=db,
        page=page,
        per_page=per_page,
        status=status,
        customer_id=customer_id,
        customer_name=customer_name,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        sales_person_id=sales_person_id
    )
    
    return PaginatedResponse(
        items=[ContractResponse.from_orm(item) for item in items],
        pagination=PaginationModel(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page
        )
    )


@router.post("/upload-and-parse", response_model=ContractParseResult, status_code=status.HTTP_202_ACCEPTED)
async def upload_and_parse_contract(
    file: UploadFile = File(...),
    customer_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传合同并启动AI解析"""
    # 验证文件类型
    allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}"
        )

    # 验证文件大小
    content = await file.read()
    file_size = len(content)
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件过大，最大允许 {settings.MAX_FILE_SIZE // 1048576}MB"
        )
    await file.seek(0)  # 重置文件指针

    # 通过魔数字节验证文件真实类型
    from app.utils.file_utils import validate_file_magic
    if not validate_file_magic(content, ['jpeg', 'png', 'pdf']):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容与声明的类型不匹配"
        )

    # 保存文件
    relative_path, file_hash, file_size = await save_uploaded_file(
        file=file,
        base_dir=settings.CONTRACT_UPLOAD_DIR,
        sub_dir=""
    )

    # 生成合同编号（加入随机后缀防并发冲突）
    from datetime import datetime
    import uuid
    contract_number = f"HT{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"

    # 创建合同记录（草稿状态）
    contract_data = ContractCreate(
        contract_number=contract_number,
        title=file.filename,
        customer_id=customer_id,
        currency="CNY",
        total_amount=Decimal('0'),
        original_file_path=relative_path,
        file_hash=file_hash,
        signed_date=None
    )

    contract = ContractService.create_contract(
        db=db,
        contract_data=contract_data,
        sales_person_id=current_user.id
    )

    # TODO: 提交异步AI解析任务
    # task_id = submit_parse_task(contract.id, relative_path)

    return ContractParseResult(
        task_id="mock-task-id",
        status="parsing",
        contract_id=contract.id,
        message="合同上传成功，正在AI解析中..."
    )


@router.get("/parse-status/{contract_id}")
def get_parse_status(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询合同解析状态"""
    contract = ContractService.get_contract(db, contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    # 根据合同当前状态判断解析进度
    if contract.status == 'draft' and not contract.contract_data:
        return ResponseModel(code=200, data={
            "status": "processing",
            "progress": 50,
            "message": "正在调用AI解析合同内容..."
        })

    return ResponseModel(code=200, data={
        "status": "completed",
        "progress": 100,
        "contract_id": contract.id,
        "parsed_data": contract.contract_data,
        "confidence": float(contract.confidence) if contract.confidence else None
    })


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同详情"""
    contract = ContractService.get_contract(db, contract_id)

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )

    # 填充 customer_name
    if contract.customer_id:
        from app.models.customer import Customer
        customer = db.query(Customer).filter(Customer.id == contract.customer_id).first()
        contract.customer_name = customer.name if customer else None
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    # 权限检查
    if current_user.role != "admin" and contract.sales_person_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此合同"
        )
    
    return contract


@router.put("/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: int,
    contract_data: ContractUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新合同"""
    contract = ContractService.get_contract(db, contract_id)
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    # 权限检查
    if current_user.role != "admin" and contract.sales_person_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此合同"
        )
    
    updated_contract = ContractService.update_contract(db, contract_id, contract_data)
    
    return updated_contract


@router.delete("/{contract_id}")
def delete_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除合同"""
    contract = ContractService.get_contract(db, contract_id)
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    # 权限检查（仅管理员可删除）
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可删除合同"
        )
    
    success = ContractService.delete_contract(db, contract_id)
    
    if success:
        return {"message": "删除成功"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除失败"
        )


@router.post("/{contract_id}/confirm-parsed-data", response_model=ContractResponse)
def confirm_parsed_data(
    contract_id: int,
    parsed_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """确认或修正AI解析结果"""
    contract = ContractService.get_contract(db, contract_id)
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    # 权限检查
    if current_user.role != "admin" and contract.sales_person_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此合同"
        )
    
    # 更新解析数据
    confidence = parsed_data.get('confidence', 0.9)
    updated_contract = ContractService.update_contract_data(
        db=db,
        contract_id=contract_id,
        contract_data=parsed_data.get('data', {}),
        confidence=confidence
    )
    
    return updated_contract
