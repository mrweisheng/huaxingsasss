"""
付款管理API路由
"""
import asyncio
import logging
import os
import shutil
from typing import Optional
from decimal import Decimal
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from app.db.session import get_db
from app.schemas.payment import (
    PaymentCreate, PaymentUpdate, PaymentResponse, PaymentPlanCreate,
    ReceiptAnalysisData, ReceiptAnalyzeResponse, PendingMatchItem,
    CreateFromReceiptRequest,
)
from app.schemas.response import ResponseModel, PaginatedResponse, PaginationModel
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.payment import Payment
from app.models.contract import Contract
from app.models.customer import Customer
from app.services.payment_service import PaymentService
from app.services.receipt_analyzer import ReceiptAnalyzer
from app.utils.file_utils import save_uploaded_file, generate_unique_filename
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[PaymentResponse])
def list_payments(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    contract_id: Optional[int] = Query(None, description="合同ID"),
    keyword: Optional[str] = Query(None, description="搜索关键词（合同编号/客户名称）"),
    status: Optional[str] = Query(None, description="付款状态"),
    payment_type: Optional[str] = Query(None, alias="type", description="类型: income/expense"),
    date_from: Optional[date] = Query(None, description="付款日期起"),
    date_to: Optional[date] = Query(None, description="付款日期止"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取付款记录列表"""
    query = db.query(Payment).filter(Payment.is_deleted == False)\
        .outerjoin(Contract, Payment.contract_id == Contract.id)\
        .outerjoin(Customer, Contract.customer_id == Customer.id)

    if contract_id:
        query = query.filter(Payment.contract_id == contract_id)
    if keyword:
        query = query.filter(
            Contract.contract_number.ilike(f'%{keyword}%') |
            Customer.name.ilike(f'%{keyword}%')
        )
    if status:
        query = query.filter(Payment.status == status)
    if payment_type:
        query = query.filter(Payment.type == payment_type)
    if date_from:
        query = query.filter(Payment.paid_date >= date_from)
    if date_to:
        query = query.filter(Payment.paid_date <= date_to)

    # 角色权限：income 只看收入+自己合同，expense 只看支出+自己创建的，admin 全量
    if current_user.role == "income":
        query = query.filter(Payment.type == "income")
        query = query.filter(Contract.sales_person_id == current_user.id)
    elif current_user.role == "expense":
        query = query.filter(Payment.type == "expense")
        query = query.filter(Payment.created_by == current_user.id)

    total = query.count()
    items = query.order_by(Payment.paid_date.desc().nullsfirst(), Payment.created_at.desc())\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()

    # 填充 contract_number 和 customer_name
    for item in items:
        contract = db.query(Contract).filter(Contract.id == item.contract_id).first()
        if contract:
            item.contract_number = contract.contract_number
            if contract.customer_id:
                customer = db.query(Customer).filter(Customer.id == contract.customer_id).first()
                item.customer_name = customer.name if customer else None

    return PaginatedResponse(
        items=[PaymentResponse.model_validate(item) for item in items],
        pagination=PaginationModel(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page
        )
    )


@router.post("/upload-receipt", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    contract_id: int = Form(...),
    installment_number: int = Form(...),
    currency: str = Form("CNY"),
    paid_amount: Decimal = Form(...),
    paid_date: date = Form(...),
    payment_method: str = Form(...),
    payment_type: str = Form("income"),
    payee_name: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传付款凭证并登记"""
    # 角色强制 type 一致
    if current_user.role == "income" and payment_type != "income":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="income角色只能创建收入记录")
    if current_user.role == "expense" and payment_type != "expense":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色只能创建支出记录")

    receipt_path = None

    if file:
        # 验证文件大小
        content = await file.read()
        if len(content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件过大，最大允许 {settings.MAX_FILE_SIZE // 1048576}MB"
            )
        await file.seek(0)

        relative_path, file_hash, file_size = await save_uploaded_file(
            file=file,
            base_dir=settings.RECEIPT_UPLOAD_DIR,
            sub_dir=""
        )
        receipt_path = relative_path

    payment = PaymentService.create_payment_with_exchange_rate(
        db=db,
        contract_id=contract_id,
        installment_number=installment_number,
        currency=currency,
        amount=paid_amount,
        paid_date=paid_date,
        payment_method=payment_method,
        receipt_image_path=receipt_path,
        notes=notes,
        created_by=current_user.id,
        type=payment_type,
        payee_name=payee_name,
    )

    return payment


def _validate_temp_path(temp_file_path: str) -> str:
    """校验 temp_file_path 在 TEMP_UPLOAD_DIR 内，防止路径穿越。
    返回规范化的绝对路径。"""
    real = os.path.realpath(temp_file_path)
    allowed_prefix = os.path.realpath(settings.TEMP_UPLOAD_DIR)
    if not real.startswith(allowed_prefix + os.sep) and real != allowed_prefix:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="非法临时文件路径",
        )
    return real


def _move_temp_to_permanent(temp_file_path: str) -> str:
    """将临时文件从 TEMP_UPLOAD_DIR 移动到 RECEIPT_UPLOAD_DIR/YYYY/MM/，
    返回永久相对路径。源文件不存在时返回空字符串。"""
    real_path = _validate_temp_path(temp_file_path)
    if not os.path.exists(real_path):
        return ""
    year_month = datetime.now().strftime("%Y/%m")
    target_dir = Path(settings.RECEIPT_UPLOAD_DIR) / year_month
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = os.path.basename(real_path)
    target_path = target_dir / filename
    shutil.move(real_path, str(target_path))
    return str(Path(year_month) / filename)


@router.post("/analyze-receipt", response_model=ReceiptAnalyzeResponse, status_code=status.HTTP_200_OK)
async def analyze_receipt(
    contract_id: int = Form(...),
    payment_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传凭证文件 + 合同上下文 → AI 分析 + 匹配建议"""
    # 角色强制 type 一致
    if current_user.role == "income" and payment_type != "income":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="income角色只能分析收入凭证")
    if current_user.role == "expense" and payment_type != "expense":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色只能分析支出凭证")

    # 校验合同存在 + 权限
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")
    if current_user.role == "income" and contract.sales_person_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此合同")

    # 读取文件并验证大小
    file_content = await file.read()
    if len(file_content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件过大，最大允许 {settings.MAX_FILE_SIZE // 1048576}MB",
        )

    # 保存到 TEMP_UPLOAD_DIR/{user_id}/
    user_temp_dir = Path(settings.TEMP_UPLOAD_DIR) / str(current_user.id)
    user_temp_dir.mkdir(parents=True, exist_ok=True)
    unique_filename = generate_unique_filename(file.filename or "receipt.bin")
    temp_file_path = str(user_temp_dir / unique_filename)
    with open(temp_file_path, "wb") as f:
        f.write(file_content)

    # AI 分析（同步，用 asyncio.to_thread 避免阻塞事件循环）
    try:
        analysis_result = await asyncio.to_thread(
            ReceiptAnalyzer.analyze_from_file, temp_file_path, file.filename or "receipt"
        )
    except Exception as e:
        logger.exception("ReceiptAnalyzer 分析失败: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI 分析失败: {e}")

    if not analysis_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=analysis_result.get("error", "分析失败"),
        )

    # 构建 ReceiptAnalysisData
    data = analysis_result["data"] or {}
    analysis_data = ReceiptAnalysisData.model_validate(data, by_name=True)

    # 仅 income 类型：查找待匹配的 pending 记录
    pending_matches: list[PendingMatchItem] = []
    if payment_type == "income":
        pending_payments = (
            db.query(Payment)
            .filter(
                Payment.contract_id == contract_id,
                Payment.type == "income",
                Payment.status == "pending",
                Payment.is_deleted == False,
            )
            .all()
        )
        ai_amount = data.get("amount") or 0
        ai_currency = data.get("currency") or ""
        scored = []
        for p in pending_payments:
            score = 0
            amount_diff = abs(float(p.paid_amount) - float(ai_amount))
            if amount_diff < 1:
                score += 50
            elif ai_amount and amount_diff / float(ai_amount) < 0.05:
                score += 30
            if p.currency == ai_currency:
                score += 10
            if score > 0:
                scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        for score, p in scored[:5]:
            pending_matches.append(PendingMatchItem(
                payment_id=p.id,
                installment_number=p.installment_number,
                installment_name=p.installment_name,
                amount=p.paid_amount,
                currency=p.currency,
                status=p.status,
                score=score,
                match_reason=f"金额匹配度: {score}",
            ))

    # 下一个期数编号
    next_inst = PaymentService.get_next_installment_number(db, contract_id, payment_type)

    # 该合同该类型已有付款数量
    existing_count = (
        db.query(func.count(Payment.id))
        .filter(
            Payment.contract_id == contract_id,
            Payment.type == payment_type,
            Payment.is_deleted == False,
        )
        .scalar()
    )

    return ReceiptAnalyzeResponse(
        analysis=analysis_data,
        temp_file_path=temp_file_path,
        pending_matches=pending_matches,
        existing_payment_count=existing_count,
        next_installment_number=next_inst,
    )


@router.post("/create-from-receipt", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_from_receipt(
    req: CreateFromReceiptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从凭证分析结果创建/匹配付款记录"""
    payment_type = req.payment_type

    # 角色强制 type 一致
    if current_user.role == "income" and payment_type != "income":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="income角色只能创建收入记录")
    if current_user.role == "expense" and payment_type != "expense":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色只能创建支出记录")

    # 校验合同存在 + 权限
    contract = db.query(Contract).filter(Contract.id == req.contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")
    if current_user.role == "income" and contract.sales_person_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此合同")

    # 服务端二次校验必填字段
    if not req.currency:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="币种不能为空")
    if not req.paid_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="交易日期不能为空")

    # receipt_data 转为 dict（ORM 存 JSON）
    # 使用 mode='json' 把 Decimal/date 等转成 JSON 兼容类型，
    # 否则 SQLAlchemy 序列化 JSON 列时会抛 "Object of type Decimal is not JSON serializable"
    receipt_data_dict = req.receipt_data.model_dump(by_alias=True, mode='json') if req.receipt_data else None

    if req.match_payment_id is not None:
        # ── 分支 A：匹配到已有 pending 记录 ──
        payment = db.query(Payment).filter(Payment.id == req.match_payment_id).first()
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="匹配付款记录不存在")
        if payment.contract_id != req.contract_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="匹配记录不属于该合同")
        if payment.type != payment_type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="匹配记录类型不匹配")
        if payment.status != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能匹配待确认状态的记录")

        # 迁移临时文件
        permanent_path = _move_temp_to_permanent(req.temp_file_path)

        # 更新 pending 记录
        update_data = PaymentUpdate(
            receipt_image_path=permanent_path or None,
            receipt_data=receipt_data_dict,
            paid_date=req.paid_date,
            payment_method=req.payment_method,
            installment_name=req.installment_name,
            notes=req.notes,
        )
        updated = PaymentService.update_payment(db, payment.id, update_data)
        return updated

    else:
        # ── 分支 B：创建新记录（服务端实时重算 installment_number）──
        real_installment_number = PaymentService.get_next_installment_number(
            db, req.contract_id, payment_type
        )

        # 迁移临时文件
        permanent_path = _move_temp_to_permanent(req.temp_file_path)

        payment = PaymentService.create_payment_with_exchange_rate(
            db=db,
            contract_id=req.contract_id,
            installment_number=real_installment_number,
            currency=req.currency,
            amount=req.amount,
            paid_date=req.paid_date,
            payment_method=req.payment_method or "unknown",
            receipt_image_path=permanent_path or None,
            notes=req.notes,
            created_by=current_user.id,
            type=payment_type,
            payee_name=req.payee_name,
            installment_name=req.installment_name,
            receipt_data=receipt_data_dict,
        )
        return payment


@router.get("/contract/{contract_id}")
def get_contract_payments(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同的付款记录（按角色过滤类型）"""
    if current_user.role == "income":
        type_filter = "income"
    elif current_user.role == "expense":
        type_filter = "expense"
    else:
        type_filter = None

    result = PaymentService.get_contract_payments(db, contract_id, type_filter=type_filter)

    return ResponseModel(
        code=200,
        message="success",
        data=result
    )


@router.get("/{payment_id}/receipt")
def get_receipt_image(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查看付款凭证图片"""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="付款记录不存在")

    # 权限检查：admin 全量，income 只看自己合同，expense 只看自己创建的
    contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()
    if current_user.role == "income" and contract and contract.sales_person_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    if current_user.role == "expense" and payment.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")

    if not payment.receipt_image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证文件不存在")

    file_path = Path(settings.RECEIPT_UPLOAD_DIR) / payment.receipt_image_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证文件已丢失")

    media_type = "application/octet-stream"
    suffix = file_path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif suffix == ".png":
        media_type = "image/png"

    return FileResponse(path=str(file_path), media_type=media_type)


@router.delete("/{payment_id}")
def delete_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除付款记录"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可删除付款记录"
        )

    success = PaymentService.delete_payment(db, payment_id, user_id=current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="付款记录不存在"
        )

    return {"message": "删除成功"}
