"""
汇率管理API路由
"""
from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import date

from app.db.session import get_db
from app.api.dependencies import get_current_user, require_role
from app.models.user import User
from app.models.exchange_rate import ExchangeRate
from app.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateResponse
from app.schemas.response import ResponseModel
from app.services.exchange_rate_service import ExchangeRateService

router = APIRouter()


@router.get("/latest", response_model=ResponseModel)
def get_latest_rate(
    from_currency: str = Query("HKD", description="源币种"),
    to_currency: str = Query("CNY", description="目标币种"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取最新汇率（含日期和来源信息，单次查询）"""
    rate_record = ExchangeRateService.get_exchange_rate_record(
        db, from_currency, to_currency, date.today()
    )

    if rate_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到 {from_currency} -> {to_currency} 的汇率"
        )

    return ResponseModel(
        code=200,
        message="success",
        data={
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": float(rate_record.rate),
            "rate_date": str(rate_record.rate_date),
            "source": rate_record.source or "fallback"
        }
    )


@router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
def create_exchange_rate(
    rate_data: ExchangeRateCreate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """手动录入汇率（管理员/财务权限）"""
    ExchangeRateService.update_exchange_rate(
        db=db,
        from_currency=rate_data.from_currency,
        to_currency=rate_data.to_currency,
        rate=rate_data.rate,
        rate_date=rate_data.rate_date,
        source=rate_data.source,
        created_by=current_user.id
    )

    return ResponseModel(
        code=201,
        message="汇率录入成功",
        data={
            "from_currency": rate_data.from_currency,
            "to_currency": rate_data.to_currency,
            "rate": float(rate_data.rate),
            "rate_date": str(rate_data.rate_date),
            "source": rate_data.source
        }
    )


@router.get("/history", response_model=ResponseModel)
def get_rate_history(
    from_currency: str = Query("HKD", description="源币种"),
    to_currency: str = Query("CNY", description="目标币种"),
    limit: int = Query(30, ge=1, le=365, description="返回条数"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取汇率历史记录"""
    records = db.query(ExchangeRate).filter(
        ExchangeRate.from_currency == from_currency,
        ExchangeRate.to_currency == to_currency,
        ExchangeRate.is_active == True
    ).order_by(
        ExchangeRate.rate_date.desc()
    ).limit(limit).all()

    return ResponseModel(
        code=200,
        message="success",
        data=[
            {
                "rate": float(r.rate),
                "rate_date": str(r.rate_date),
                "source": r.source,
            }
            for r in records
        ]
    )
