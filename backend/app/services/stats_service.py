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
        """构建最近 N 个月的收入/支出趋势（按币种分组，不跨币种合并）"""
        today = date.today()
        # 从当月开始往前推 N 个月
        start_month = today.month - months + 1
        start_year = today.year
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        start_date = date(start_year, start_month, 1)

        # 查询 paid 状态的付款，按月+类型+币种汇总原始金额
        rows = db.query(
            extract("year", Payment.paid_date).label("yr"),
            extract("month", Payment.paid_date).label("mo"),
            Payment.type,
            Payment.currency,
            func.sum(Payment.paid_amount).label("total"),
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

        # 按月+币种聚合：每个月的每个币种独立累加
        # 结构: {month_key: {currency: {"income": D, "expense": D}}}
        monthly = defaultdict(lambda: {"CNY": {"income": Decimal("0"), "expense": Decimal("0")},
                                       "HKD": {"income": Decimal("0"), "expense": Decimal("0")}})

        for row in rows:
            month_key = f"{int(row.yr):04d}-{int(row.mo):02d}"
            cur = row.currency if row.currency in ("CNY", "HKD") else "CNY"
            bucket = monthly[month_key][cur]
            if row.type == "income":
                bucket["income"] += row.total or Decimal("0")
            elif row.type == "expense":
                bucket["expense"] += row.total or Decimal("0")

        # 生成完整的月份列表
        result = []
        for i in range(months):
            m = today.month - months + 1 + i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            month_key = f"{y:04d}-{m:02d}"
            by_cur = monthly.get(month_key, {"CNY": {"income": Decimal("0"), "expense": Decimal("0")},
                                              "HKD": {"income": Decimal("0"), "expense": Decimal("0")}})
            result.append({
                "month": month_key,
                "income": {
                    "CNY": by_cur["CNY"]["income"],
                    "HKD": by_cur["HKD"]["income"],
                },
                "expense": {
                    "CNY": by_cur["CNY"]["expense"],
                    "HKD": by_cur["HKD"]["expense"],
                },
                "profit": {
                    "CNY": by_cur["CNY"]["income"] - by_cur["CNY"]["expense"],
                    "HKD": by_cur["HKD"]["income"] - by_cur["HKD"]["expense"],
                },
            })

        return result

    @staticmethod
    def _build_business_type_distribution(db: Session) -> list:
        """按业务类型分布（按币种分组）"""
        # 按 (business_type, currency) 分组聚合合同原始金额（合同主币种）
        income_by_cur = func.sum(Contract.paid_amount).label("income")
        expense_by_cur = func.sum(Contract.total_expense).label("expense")
        total_by_cur = func.sum(Contract.total_amount).label("total")

        rows = db.query(
            Contract.business_type,
            Contract.currency,
            func.count(Contract.id).label("contract_count"),
            income_by_cur,
            expense_by_cur,
            total_by_cur,
        ).filter(
            Contract.is_deleted == False,
        ).group_by(Contract.business_type, Contract.currency).all()

        # 合并到业务类型维度：每个业务类型下按币种拆
        by_bt: dict[str, dict] = {}
        for row in rows:
            bt = BusinessType.normalize(row.business_type) or row.business_type or "其他"
            cur = row.currency if row.currency in ("CNY", "HKD") else "CNY"
            if bt not in by_bt:
                by_bt[bt] = {
                    "business_type": bt,
                    "contract_count": 0,
                    "total_amount": {"CNY": Decimal("0"), "HKD": Decimal("0")},
                    "income": {"CNY": Decimal("0"), "HKD": Decimal("0")},
                    "expense": {"CNY": Decimal("0"), "HKD": Decimal("0")},
                    "profit": {"CNY": Decimal("0"), "HKD": Decimal("0")},
                }
            by_bt[bt]["contract_count"] += row.contract_count or 0
            by_bt[bt]["total_amount"][cur] += row.total or Decimal("0")
            by_bt[bt]["income"][cur] += row.income or Decimal("0")
            by_bt[bt]["expense"][cur] += row.expense or Decimal("0")
            by_bt[bt]["profit"][cur] = (
                by_bt[bt]["income"][cur] - by_bt[bt]["expense"][cur]
            )

        result = list(by_bt.values())
        # 按 CNY 业务量（不跨币种比较）作为排序参考；不强行混币种排名
        result.sort(key=lambda x: (x["profit"]["CNY"] + x["profit"]["HKD"]), reverse=True)
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
