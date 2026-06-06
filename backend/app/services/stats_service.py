"""
财务统计服务
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from sqlalchemy import func, case, extract
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.payment import Payment
from app.models.customer import Customer
from app.core.business_types import BusinessType

logger = logging.getLogger(__name__)


class StatsService:
    """财务统计服务"""

    @staticmethod
    def get_financial_overview(db: Session) -> dict:
        """获取财务总览数据（admin 全量）"""

        # ── 1. 核心 KPI ──
        kpi = StatsService._build_kpi(db)

        # ── 2. 月度趋势（最近 6 个月） ──
        monthly_trend = StatsService._build_monthly_trend(db)

        # ── 3. 业务类型分布 ──
        business_dist = StatsService._build_business_type_distribution(db)

        # ── 4. TOP 10 客户 ──
        top_customers = StatsService._build_top_customers(db)

        # ── 5. 合同状态分布 ──
        contract_status = StatsService._build_contract_status(db)

        return {
            "kpi": kpi,
            "monthly_trend": monthly_trend,
            "business_type_distribution": business_dist,
            "top_customers": top_customers,
            "contract_status": contract_status,
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
    def _build_monthly_trend(db: Session, months: int = 6) -> list:
        """构建最近 N 个月的收入/支出趋势（统一折算 CNY）"""
        today = date.today()
        # 从当月开始往前推 N 个月
        start_month = today.month - months + 1
        start_year = today.year
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        start_date = date(start_year, start_month, 1)

        # 查询 paid 状态的付款，按月+类型汇总
        rows = db.query(
            extract("year", Payment.paid_date).label("yr"),
            extract("month", Payment.paid_date).label("mo"),
            Payment.type,
            Payment.currency,
            func.sum(Payment.paid_amount).label("total"),
            func.sum(Payment.paid_amount_in_cny).label("total_cny"),
        ).filter(
            Payment.is_deleted == False,
            Payment.status == "paid",
            Payment.paid_date >= start_date,
        ).group_by(
            extract("year", Payment.paid_date),
            extract("month", Payment.paid_date),
            Payment.type,
            Payment.currency,
        ).all()

        # 按月聚合：CNY 付款直接用 paid_amount，HKD 付款用 paid_amount_in_cny
        monthly_income = defaultdict(Decimal)
        monthly_expense = defaultdict(Decimal)

        for row in rows:
            month_key = f"{int(row.yr):04d}-{int(row.mo):02d}"
            # CNY 付款的 paid_amount_in_cny 为 None（不需要折算），直接用 paid_amount
            amount_cny = row.total_cny if row.total_cny else row.total
            if row.type == "income":
                monthly_income[month_key] += amount_cny
            else:
                monthly_expense[month_key] += amount_cny

        # 生成完整的月份列表
        result = []
        for i in range(months):
            m = today.month - months + 1 + i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            month_key = f"{y:04d}-{m:02d}"
            inc = monthly_income.get(month_key, Decimal("0"))
            exp = monthly_expense.get(month_key, Decimal("0"))
            result.append({
                "month": month_key,
                "income": inc,
                "expense": exp,
                "profit": inc - exp,
            })

        return result

    @staticmethod
    def _build_business_type_distribution(db: Session) -> list:
        """按业务类型分布（统一折算 CNY）"""
        income_cny = func.sum(
            func.coalesce(func.nullif(Contract.paid_amount_in_cny, 0), Contract.paid_amount)
        ).label("income")
        expense_cny = func.sum(
            func.coalesce(func.nullif(Contract.total_expense_in_cny, 0), Contract.total_expense)
        ).label("expense")

        rows = db.query(
            Contract.business_type,
            func.count(Contract.id).label("contract_count"),
            income_cny,
            expense_cny,
        ).filter(
            Contract.is_deleted == False,
        ).group_by(Contract.business_type).all()

        result = []
        for row in rows:
            bt = BusinessType.normalize(row.business_type) or row.business_type or "其他"
            inc = row.income or Decimal("0")
            exp = row.expense or Decimal("0")
            result.append({
                "business_type": bt,
                "contract_count": row.contract_count,
                "total_amount": Decimal("0"),
                "income": inc,
                "expense": exp,
                "profit": inc - exp,
            })

        result.sort(key=lambda x: x["profit"], reverse=True)
        return result

    @staticmethod
    def _build_top_customers(db: Session, limit: int = 10) -> list:
        """按客户收入排名（统一折算 CNY）"""
        income_cny = func.sum(
            func.coalesce(func.nullif(Contract.paid_amount_in_cny, 0), Contract.paid_amount)
        ).label("total_income")
        expense_cny = func.sum(
            func.coalesce(func.nullif(Contract.total_expense_in_cny, 0), Contract.total_expense)
        ).label("total_expense")

        rows = db.query(
            Customer.id.label("customer_id"),
            Customer.name.label("customer_name"),
            func.count(Contract.id).label("contract_count"),
            income_cny,
            expense_cny,
        ).join(
            Contract, Contract.customer_id == Customer.id
        ).filter(
            Contract.is_deleted == False,
            Customer.is_deleted == False,
        ).group_by(
            Customer.id, Customer.name,
        ).order_by(
            income_cny.desc(),
        ).limit(limit).all()

        return [
            {
                "customer_id": r.customer_id,
                "customer_name": r.customer_name,
                "contract_count": r.contract_count,
                "total_income": r.total_income or Decimal("0"),
                "total_expense": r.total_expense or Decimal("0"),
                "profit": (r.total_income or Decimal("0")) - (r.total_expense or Decimal("0")),
            }
            for r in rows
        ]

    @staticmethod
    def _build_contract_status(db: Session) -> list:
        """合同状态分布"""
        rows = db.query(
            Contract.status,
            func.count(Contract.id).label("count"),
        ).filter(
            Contract.is_deleted == False,
        ).group_by(Contract.status).all()

        status_labels = {
            "draft": "草稿",
            "active": "进行中",
            "completed": "已完成",
            "cancelled": "已取消",
        }

        return [
            {"status": status_labels.get(r.status, r.status), "count": r.count}
            for r in rows
        ]
