"""
汇率服务
"""
import logging
from decimal import Decimal
from datetime import date, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models.exchange_rate import ExchangeRate
from app.config import settings

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """汇率管理服务"""

    FALLBACK_RATES = {
        ("HKD", "CNY"): Decimal(str(getattr(settings, "DEFAULT_EXCHANGE_RATE_HKD_CNY", "0.92"))),
        ("USD", "CNY"): Decimal(str(getattr(settings, "DEFAULT_EXCHANGE_RATE_USD_CNY", "7.25"))),
    }

    @staticmethod
    def get_exchange_rate(
        db: Session,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Optional[Decimal]:
        """
        获取指定日期的汇率

        查找优先级：
        1. 数据库精确日期匹配
        2. API 自动获取（frankfurter.dev → open.er-api.com）并存库
        3. 数据库 30 天内最近 / 系统默认
        4. 硬编码 fallback

        Args:
            from_currency: 源币种（HKD/USD等）
            to_currency: 目标币种（默认CNY）
            rate_date: 汇率日期

        Returns:
            汇率值 Decimal，如果找不到则返回配置中的默认值
        """
        if from_currency == to_currency:
            return Decimal('1.0')

        # 1. 精确日期匹配
        exact = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.is_active == True
        ).first()
        if exact:
            return exact.rate

        # 2. API 按需获取（查不到精确日期时自动调 API）
        fetched = ExchangeRateService._fetch_and_save_rate(
            db, from_currency, to_currency, rate_date
        )
        if fetched:
            return fetched

        # 3+4. 30天内最近 / 系统默认 / 硬编码 fallback
        record = ExchangeRateService._query_rate_record(db, from_currency, to_currency, rate_date)
        if record:
            return record.rate

        fallback = ExchangeRateService.FALLBACK_RATES.get((from_currency.upper(), to_currency.upper()))
        if fallback:
            logger.warning(
                "汇率 fallback 到硬编码: %s/%s, date=%s, rate=%s",
                from_currency, to_currency, rate_date, fallback,
            )
            return fallback

        return None

    @staticmethod
    def _fetch_and_save_rate(
        db: Session,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Optional[Decimal]:
        """
        从 API 获取指定日期汇率并存入数据库。

        仅在数据库无精确日期记录时调用，避免重复请求。
        返回获取到的汇率值，失败返回 None。
        """
        if to_currency != "CNY":
            return None

        try:
            from app.services.exchange_rate_fetcher import fetch_rate_for_date
            result = fetch_rate_for_date(from_currency, rate_date)
            if result and result.get("rate"):
                rate = Decimal(str(result["rate"]))
                actual_date = date.fromisoformat(result["actual_date"]) if isinstance(result["actual_date"], str) else result["actual_date"]
                source = result["source"]

                # 存入数据库（用 API 返回的实际日期，可能是最近工作日）
                ExchangeRateService.update_exchange_rate(
                    db=db,
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate=rate,
                    rate_date=actual_date,
                    source=source,
                )
                logger.info(
                    "API 自动获取汇率: %s/%s = %s, date=%s, source=%s",
                    from_currency, to_currency, rate, actual_date, source,
                )
                return rate
        except Exception as e:
            logger.warning(
                "API 自动获取汇率失败: %s/%s, date=%s, error=%s",
                from_currency, to_currency, rate_date, e,
            )
        return None

    @staticmethod
    def get_exchange_rate_record(
        db: Session,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Optional[ExchangeRate]:
        """
        获取指定日期的汇率记录（含日期、来源等完整信息）

        与 get_exchange_rate 不同，此方法返回完整 ORM 对象，
        避免 API 层二次查询数据库获取日期和来源信息。
        """
        if from_currency == to_currency:
            # 返回一个虚拟对象（同币种）
            return ExchangeRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=Decimal('1.0'),
                rate_date=rate_date,
                source='system',
            )

        return ExchangeRateService._query_rate_record(db, from_currency, to_currency, rate_date)

    @staticmethod
    def _query_rate_record(
        db: Session,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Optional[ExchangeRate]:
        """
        查询汇率记录的核心逻辑

        查找优先级：
        1. 当日汇率
        2. 30 天内最近汇率
        3. 系统默认汇率
        4. None（调用方处理 fallback）
        """
        start_date = rate_date - timedelta(days=30)

        rate_record = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.rate_date >= start_date,
            ExchangeRate.rate_date <= rate_date,
            ExchangeRate.is_active == True
        ).order_by(
            ExchangeRate.rate_date.desc()
        ).first()

        if rate_record:
            return rate_record

        default_record = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.source == 'system',
            ExchangeRate.is_active == True
        ).order_by(
            ExchangeRate.rate_date.desc()
        ).first()

        if default_record:
            return default_record

        return None
    
    @staticmethod
    def convert_to_cny(
        db: Session,
        amount: Decimal,
        from_currency: str,
        rate_date: date
    ) -> Tuple[Decimal, Decimal]:
        """
        将金额转换为CNY

        Returns:
            (汇率, 折算后CNY金额)
        """
        exchange_rate = ExchangeRateService.get_exchange_rate(
            db, from_currency, 'CNY', rate_date
        )

        if exchange_rate is None:
            raise ValueError(f"无法获取 {from_currency} 兑 CNY 的汇率（日期：{rate_date}）")

        amount_in_cny = amount * exchange_rate

        return exchange_rate, amount_in_cny

    @staticmethod
    def convert_currency(
        db: Session,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Tuple[Decimal, Decimal]:
        """
        将金额从一种货币直接折算为另一种货币。
        同币种返回原值，不同币种通过 CNY 交叉汇率一步完成。

        Returns:
            (交叉汇率, 折算后金额)
            交叉汇率 = 1 单位 from_currency 可兑换多少 to_currency
        """
        if from_currency == to_currency:
            return Decimal('1.0'), amount

        from_to_cny = ExchangeRateService.get_exchange_rate(
            db, from_currency, 'CNY', rate_date
        )
        if from_to_cny is None:
            raise ValueError(f"无法获取 {from_currency} 兑 CNY 的汇率（日期：{rate_date}）")

        to_to_cny = ExchangeRateService.get_exchange_rate(
            db, to_currency, 'CNY', rate_date
        )
        if to_to_cny is None:
            raise ValueError(f"无法获取 {to_currency} 兑 CNY 的汇率（日期：{rate_date}）")

        cross_rate = from_to_cny / to_to_cny
        converted = (amount * cross_rate).quantize(Decimal('0.01'))

        return cross_rate, converted
    
    @staticmethod
    def update_exchange_rate(
        db: Session,
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        rate_date: date,
        source: str = 'manual',
        created_by: int = None
    ):
        """更新或创建汇率记录"""
        existing = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.rate_date == rate_date
        ).first()
        
        if existing:
            existing.rate = rate
            existing.source = source
            existing.is_active = True
        else:
            new_rate = ExchangeRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                rate_date=rate_date,
                source=source,
                is_active=True,
                created_by=created_by
            )
            db.add(new_rate)
        
        db.commit()
