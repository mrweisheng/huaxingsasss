"""
付款管理API路由
"""
import logging
import os
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import date

from app.db.session import get_db
from app.schemas.payment import PaymentResponse, PaymentCreate, PaymentUpdate
from app.schemas.response import ResponseModel, PaginatedResponse, PaginationModel
from app.api.dependencies import get_current_user
from app.core.permissions import Role, is_admin
from app.models.user import User
from app.models.payment import Payment
from app.models.contract import Contract
from app.models.customer import Customer
from app.services.payment_service import PaymentService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_receipt_file_id(file_id: str, user_id: int):
    """把上传返回的 file_id 解析为 (绝对路径, 文件哈希)。

    复用 file_utils.resolve_file_path（兼容 AGENT_FILE_DIR / TEMP_UPLOAD_DIR）。
    """
    from app.utils.file_utils import resolve_file_path, calculate_file_hash
    path = resolve_file_path(file_id, user_id)
    if not path or not os.path.isfile(path):
        return None, None
    with open(path, "rb") as f:
        file_hash = calculate_file_hash(f.read())
    return path, file_hash


def _enforce_type_permission(current_user: User, payment_type: str):
    """收支角色隔离：income 角色只能录收入，expense 角色只能录支出，admin 全量。"""
    if current_user.role == Role.INCOME and payment_type != "income":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="收入角色只能录入收入")
    if current_user.role == Role.EXPENSE and payment_type != "expense":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="支出角色只能录入支出")


@router.post("", response_model=ResponseModel[PaymentResponse])
def create_payment(
    payload: PaymentCreate,
    contract_id: int = Query(..., description="合同ID（从合同卡片入口带入）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """表单创建付款记录（收入/支出统一入口）。

    - 收入：凭证必传，创建后立即落 pending + verification_status=pending，异步校验通过才结算。
    - 支出：有凭证→paid 结算（弱校验提醒）；无凭证(no_receipt)→paid 结算。
    """
    _enforce_type_permission(current_user, payload.type)

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    # 解析凭证 file_id → 绝对路径
    receipt_path = None
    receipt_hash = None
    if payload.receipt_file_id:
        receipt_path, receipt_hash = _resolve_receipt_file_id(payload.receipt_file_id, current_user.id)
        if not receipt_path:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="凭证文件不存在，请重新上传")

    # 收入必须校验凭证存在（schema 已校验 receipt_file_id，这里再确认文件能解析）
    if payload.type == "income" and not receipt_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="收入必须上传有效凭证")

    try:
        payment = PaymentService.create_payment_from_form(
            db=db,
            contract_id=contract_id,
            payload=payload,
            created_by=current_user.id,
            receipt_path=receipt_path,
            receipt_file_hash=receipt_hash,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 收入有凭证 → 投递异步校验 task
    if payload.type == "income" and receipt_path:
        from app.tasks.receipt_verification_tasks import verify_receipt
        verify_receipt.delay(payment.id)
        logger.info("已投递凭证校验任务: payment_id=%d", payment.id)
    # 支出有凭证 → 投递弱校验 task（不阻断结算）
    elif payload.type == "expense" and receipt_path:
        from app.tasks.receipt_verification_tasks import verify_receipt
        verify_receipt.delay(payment.id)

    return ResponseModel(code=201, message="创建成功", data=PaymentResponse.model_validate(payment))


@router.post("/upload", response_model=ResponseModel)
async def upload_receipt(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """表单凭证上传（复用 agent upload 的落盘逻辑，返回 file_id 供创建/编辑接口引用）。

    与 /agent/upload 区别：这里不落 agent_file 表（不绑定会话），只返回 file_id，
    由创建/编辑接口在表单提交时解析为绝对路径存入 receipt_image_path。
    """
    import uuid
    user_dir = os.path.join(settings.AGENT_FILE_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件过大")

    file_id = str(uuid.uuid4())
    original_ext = ""
    if file.filename and "." in file.filename:
        original_ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    fname_on_disk = file_id + original_ext
    file_path = os.path.join(user_dir, fname_on_disk)

    with open(file_path, "wb") as f:
        f.write(content)

    # HEIC/HEIF 转 JPEG（与 agent upload 一致）
    if original_ext in (".heic", ".heif"):
        try:
            from PIL import Image
            import io as _io
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
            except Exception:
                pass
            with Image.open(_io.BytesIO(content)) as img:
                rgb = img.convert("RGB")
                buf = _io.BytesIO()
                rgb.save(buf, format="JPEG", quality=85)
                jpeg_bytes = buf.getvalue()
            original_ext = ".jpg"
            fname_on_disk = file_id + original_ext
            new_path = os.path.join(user_dir, fname_on_disk)
            with open(new_path, "wb") as f:
                f.write(jpeg_bytes)
            if new_path != file_path:
                os.remove(file_path)
        except Exception:
            try:
                os.remove(file_path)
            except OSError:
                pass
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="HEIC 文件解码失败，请转为 JPG 后上传")

    return ResponseModel(code=200, message="上传成功",
                         data={"file_id": fname_on_disk, "original_name": file.filename})


@router.put("/{payment_id}", response_model=ResponseModel[PaymentResponse])
def update_payment_form(
    payment_id: int,
    payload: PaymentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """表单编辑付款（改字段 / 换凭证 / 清凭证）。

    收入换凭证或清凭证后会重置为待校验，并重新投递校验 task。
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="付款记录不存在")

    _enforce_type_permission(current_user, payment.type)

    # 解析新凭证
    new_receipt_path = None
    new_receipt_hash = None
    receipt_cleared = False
    if payload.receipt_file_id == "":
        # 空字符串表示清除凭证
        receipt_cleared = True
    elif payload.receipt_file_id:
        new_receipt_path, new_receipt_hash = _resolve_receipt_file_id(payload.receipt_file_id, current_user.id)
        if not new_receipt_path:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新凭证文件不存在，请重新上传")

    try:
        updated = PaymentService.update_payment_from_form(
            db=db,
            payment_id=payment_id,
            payload=payload,
            updated_by=current_user.id,
            new_receipt_path=new_receipt_path,
            new_receipt_hash=new_receipt_hash,
            receipt_cleared=receipt_cleared,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="付款记录不存在")

    # 收入且凭证有变化 → 重新投递校验
    if updated.type == "income" and (new_receipt_path or receipt_cleared) and updated.receipt_image_path:
        from app.tasks.receipt_verification_tasks import verify_receipt
        verify_receipt.delay(updated.id)

    return ResponseModel(code=200, message="更新成功", data=PaymentResponse.model_validate(updated))


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
    # 角色 → payment.type 隔离（income 看 income / expense 看 expense / admin 全量）
    if current_user.role == Role.INCOME:
        role_type_filter = "income"
    elif current_user.role == Role.EXPENSE:
        role_type_filter = "expense"
    else:
        role_type_filter = None

    items, total = PaymentService.get_payments(
        db=db,
        page=page,
        per_page=per_page,
        contract_id=contract_id,
        keyword=keyword,
        status=status,
        payment_type=payment_type,
        date_from=date_from,
        date_to=date_to,
        role_type_filter=role_type_filter,
    )

    return PaginatedResponse(
        items=[PaymentResponse.model_validate(item) for item in items],
        pagination=PaginationModel(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page
        )
    )


@router.get("/contract/{contract_id}")
def get_contract_payments(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同的付款记录（按角色过滤类型）"""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    # 合同对所有角色可见，仅按 payment.type 隔离收支
    if current_user.role == Role.INCOME:
        type_filter = "income"
    elif current_user.role == Role.EXPENSE:
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

    # 权限检查：按 payment.type 隔离收支（income 只能看收入凭证，expense 只能看支出凭证，admin 全量）
    if current_user.role == Role.INCOME and payment.type != "income":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    if current_user.role == Role.EXPENSE and payment.type != "expense":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")

    if not payment.receipt_image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证文件不存在")

    # 兼容两种存储格式：绝对路径（表单录入）直接用，相对路径（旧数据）拼接 RECEIPT_UPLOAD_DIR
    stored = payment.receipt_image_path
    if os.path.isabs(stored):
        file_path = Path(stored)
    else:
        file_path = Path(settings.RECEIPT_UPLOAD_DIR) / stored
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
    if not is_admin(current_user):
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
