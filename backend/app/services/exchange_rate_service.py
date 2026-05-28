"""
汇率服务
"""
from decimal import Decimal
from datetime import date, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models.exchange_rate import ExchangeRate
from app.config import settings


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

        Args:
            from_currency: 源币种（HKD/USD等）
            to_currency: 目标币种（默认CNY）
            rate_date: 汇率日期

        Returns:
            汇率值 Decimal，如果找不到则返回配置中的默认值
        """
        if from_currency == to_currency:
            return Decimal('1.0')

        record = ExchangeRateService._query_rate_record(db, from_currency, to_currency, rate_date)
        if record:
            return record.rate

        fallback = ExchangeRateService.FALLBACK_RATES.get((from_currency.upper(), to_currency.upper()))
        if fallback:
            return fallback

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
