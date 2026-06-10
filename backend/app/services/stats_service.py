"""
财务统计服务
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, case, cast, Date
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.customer import Customer

logger = logging.getLogger(__name__)


class StatsService:
    """财务统计服务"""

    @staticmethod
    def get_financial_overview(db: Session) -> dict:
        """获取财务总览数据（admin 全量）"""

        # ── 1. 核心 KPI ──
        kpi = StatsService._build_kpi(db)

        # ── 2. 每日业务趋势（滚动近 30 天） ──
        daily_trend = StatsService._build_daily_business_trend(db)

        # ── 3. TOP 10 客户 ──
        top_customers = StatsService._build_top_customers(db)

        return {
            "kpi": kpi,
            "daily_trend": daily_trend,
            "top_customers": top_customers,
        }

    @staticmethod
    def _build_kpi(db: Session) -> dict:
        """构建核心 KPI"""
        # 合同数
        contract_stats = db.query(
            func.count(Contract.id).label("total"),
            func.count(case((Contract.status == "active", 1))).label("active"),
        ).filter(Contract.is_deleted == False).first()

        # 客户数
        customer_count = db.query(func.count(Customer.id)).filter(
            Customer.is_deleted == False
        ).scalar()

        # 从 contracts 表直接汇总金额（比 payments 更准确）
        # 已收金额：按币种分
        income_by_currency = db.query(
            Contract.currency,
            func.sum(Contract.paid_amount).label("total"),
        ).filter(
            Contract.is_deleted == False,
        ).group_by(Contract.currency).all()

        # 待收金额
        remaining_by_currency = db.query(
            Contract.currency,
            func.sum(Contract.remaining_amount).label("total"),
        ).filter(
            Contract.is_deleted == False,
        ).group_by(Contract.currency).all()

        # 支出金额
        expense_by_currency = db.query(
            Contract.currency,
            func.sum(Contract.total_expense).label("total"),
        ).filter(
            Contract.is_deleted == False,
        ).group_by(Contract.currency).all()

        income = {"CNY": Decimal("0"), "HKD": Decimal("0")}
        remaining = {"CNY": Decimal("0"), "HKD": Decimal("0")}
        expense = {"CNY": Decimal("0"), "HKD": Decimal("0")}

        for row in income_by_currency:
            if row.currency in income:
                income[row.currency] = row.total or Decimal("0")
        for row in remaining_by_currency:
            if row.currency in remaining:
                remaining[row.currency] = row.total or Decimal("0")
        for row in expense_by_currency:
            if row.currency in expense:
                expense[row.currency] = row.total or Decimal("0")

        # 利润 = 已收 - 支出
        profit = {k: income[k] - expense[k] for k in income}

        return {
            "total_contracts": contract_stats.total or 0,
            "active_contracts": contract_stats.active or 0,
            "total_customers": customer_count or 0,
            "total_income": income,
            "total_expense": expense,
            "total_profit": profit,
            "total_remaining": remaining,
        }

    @staticmethod
    def _build_daily_business_trend(db: Session, days: int = 30) -> list:
        """构建滚动近 N 天的每日业务趋势（成交合同数 + 不重复成交客户数）。

        成交日口径：COALESCE(signed_date, created_at::date) —— 老数据可能缺签订日期，
        回退到系统录入日期，避免丢点。
        """
        today = date.today()
        start = today - timedelta(days=days - 1)

        # COALESCE(signed_date, created_at::date) AS deal_date
        deal_date = func.coalesce(Contract.signed_date, cast(Contract.created_at, Date)).label("deal_date")

        rows = db.query(
            deal_date,
            func.count(Contract.id).label("contract_count"),
            func.count(func.distinct(Contract.customer_id)).label("customer_count"),
        ).filter(
            Contract.is_deleted == False,
            func.coalesce(Contract.signed_date, cast(Contract.created_at, Date)) >= start,
            func.coalesce(Contract.signed_date, cast(Contract.created_at, Date)) <= today,
        ).group_by(deal_date).all()

        by_day = {r.deal_date: (r.contract_count or 0, r.customer_count or 0) for r in rows}

        # 补齐 30 天（含今天），缺失日期 0 填充，保证 X 轴等距
        result = []
        for i in range(days):
            d = start + timedelta(days=i)
            contract_count, customer_count = by_day.get(d, (0, 0))
            result.append({
                "date": d.isoformat(),
                "contract_count": contract_count,
                "customer_count": customer_count,
            })
        return result

    @staticmethod
    def _build_top_customers(db: Session, limit: int = 10) -> list:
        """按客户收入排名（按币种分组，不跨币种合并）"""
        rows = db.query(
            Customer.id.label("customer_id"),
            Customer.name.label("customer_name"),
            Contract.currency,
            func.count(Contract.id).label("contract_count"),
            func.sum(Contract.paid_amount).label("total_income"),
            func.sum(Contract.total_expense).label("total_expense"),
        ).join(
            Contract, Contract.customer_id == Customer.id
        ).filter(
            Contract.is_deleted == False,
            Customer.is_deleted == False,
        ).group_by(
            Customer.id, Customer.name, Contract.currency,
        ).all()

        # 合并到客户维度：每个客户下按币种拆
        by_cust: dict[int, dict] = {}
        for r in rows:
            cid = r.customer_id
            cur = r.currency if r.currency in ("CNY", "HKD") else "CNY"
            if cid not in by_cust:
                by_cust[cid] = {
                    "customer_id": cid,
                    "customer_name": r.customer_name,
                    "contract_count": 0,
                    "total_income": {"CNY": Decimal("0"), "HKD": Decimal("0")},
                    "total_expense": {"CNY": Decimal("0"), "HKD": Decimal("0")},
                    "profit": {"CNY": Decimal("0"), "HKD": Decimal("0")},
                }
            by_cust[cid]["contract_count"] += r.contract_count or 0
            by_cust[cid]["total_income"][cur] += r.total_income or Decimal("0")
            by_cust[cid]["total_expense"][cur] += r.total_expense or Decimal("0")
            by_cust[cid]["profit"][cur] = (
                by_cust[cid]["total_income"][cur] - by_cust[cid]["total_expense"][cur]
            )

        result = list(by_cust.values())
        # 按 CNY 业务量排序（admin 视角下 CNY 是主要参考币种；HKD 同理可单独看）
        result.sort(key=lambda x: x["total_income"]["CNY"] + x["total_income"]["HKD"], reverse=True)
        return result[:limit]
