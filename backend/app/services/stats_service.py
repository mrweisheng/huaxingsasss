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
from app.models.payment import Payment

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

        # ── 3. 月度收款趋势（滚动近 30 天，按币种分线） ──
        receipt_trend = StatsService._build_monthly_receipt_trend(db)

        return {
            "kpi": kpi,
            "daily_trend": daily_trend,
            "monthly_receipt_trend": receipt_trend,
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
    def _build_monthly_receipt_trend(db: Session, days: int = 30) -> list:
        """构建滚动近 N 天的每日收款趋势（按币种分线）。

        口径：以付款记录的 paid_date 为聚合日；只统计 type=income 且 paid_date 非空（已实际到账）。
        金额取 paid_amount，按 CNY/HKD 分别汇总；缺失日期 0 填充，保证 X 轴等距。
        """
        today = date.today()
        start = today - timedelta(days=days - 1)

        rows = db.query(
            Payment.paid_date.label("paid_date"),
            Payment.currency.label("currency"),
            func.sum(Payment.paid_amount).label("total"),
        ).filter(
            Payment.is_deleted == False,
            Payment.type == "income",
            Payment.paid_date.isnot(None),
            Payment.paid_date >= start,
            Payment.paid_date <= today,
        ).group_by(Payment.paid_date, Payment.currency).all()

        by_day: dict[date, dict[str, Decimal]] = {}
        for r in rows:
            cur = r.currency if r.currency in ("CNY", "HKD") else "CNY"
            slot = by_day.setdefault(r.paid_date, {"CNY": Decimal("0"), "HKD": Decimal("0")})
            slot[cur] += r.total or Decimal("0")

        result = []
        for i in range(days):
            d = start + timedelta(days=i)
            slot = by_day.get(d, {"CNY": Decimal("0"), "HKD": Decimal("0")})
            result.append({
                "date": d.isoformat(),
                "cny": slot["CNY"],
                "hkd": slot["HKD"],
            })
        return result

