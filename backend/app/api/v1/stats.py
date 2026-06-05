"""
财务统计 API 路由
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.stats import FinancialOverview
from app.schemas.response import ResponseModel
from app.api.dependencies import get_current_user, require_role
from app.models.user import User
from app.services.stats_service import StatsService
from app.core.permissions import Role

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview", response_model=ResponseModel[FinancialOverview])
def get_financial_overview(
    current_user: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """获取财务总览数据（仅 admin）"""
    data = StatsService.get_financial_overview(db)
    return ResponseModel(data=FinancialOverview(**data))
