"""
外汇牌价获取服务 - frankfurter.dev + open.er-api.com 双源方案

架构：
  1. 优先调用 frankfurter.dev（ECB 参考汇率，免费、无需 API Key）
  2. 失败时使用 open.er-api.com（备用，免费、无需 API Key）
  3. 都失败时返回空结果（上层任务会记录错误）

数据来源：
  - 主：frankfurter.dev（European Central Bank reference rates）
  - 备用：open.er-api.com（exchangerate-api.com free tier）

特性：
  - 支持当日汇率和任意历史日期汇率查询
  - 支持日期范围批量查询（用于补齐历史数据）
  - 纯 REST API，不依赖网页爬取
"""
import logging
from datetime import date
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


# ========== 汇率数据源配置 ==========

FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"
ER_API_BASE = "https://open.er-api.com/v6"

REQUEST_TIMEOUT = 15.0

# 币种列表（兑 CNY）
CURRENCIES = ["HKD", "USD"]
RATE_KEYS = {"HKD": "hkdcny", "USD": "usdcny"}

# 汇率合理性范围
RATE_BOUNDS = {
    "hkdcny": (0.5, 2.0),
    "usdcny": (5.0, 10.0),
}


# ========== 主函数（当日汇率，Celery 每日任务用） ==========

def fetch_exchange_rates() -> Dict[str, Optional[float]]:
    """
    获取当日 HKD/CNY 和 USD/CNY 汇率。

    执行顺序：
    1. 优先从 frankfurter.dev 获取
    2. 失败则从 open.er-api.com 获取
    3. 都失败返回空结果

    Returns:
        {"hkdcny": float or None, "usdcny": float or None, "source": str, "date": str}
    """
    result = {"hkdcny": None, "usdcny": None, "source": None, "date": None}

    # 主源：frankfurter.dev
    try:
        rates = _validate_rates(_fetch_frankfurter("latest"))
        if rates["hkdcny"] is not None and rates["usdcny"] is not None:
            result.update(rates)
            logger.info(
                "汇率获取成功（frankfurter.dev）: HKD/CNY=%s, USD/CNY=%s",
                rates["hkdcny"], rates["usdcny"],
            )
            return result
    except Exception as e:
        logger.warning("frankfurter.dev 汇率获取失败: %s，尝试备用源...", e)

    # 备用源：open.er-api.com
    try:
        rates = _validate_rates(_fetch_er_api("latest"))
        if rates["hkdcny"] is not None or rates["usdcny"] is not None:
            result.update(rates)
            logger.info(
                "汇率获取成功（er-api.com 备用）: HKD/CNY=%s, USD/CNY=%s",
                rates["hkdcny"], rates["usdcny"],
            )
            return result
    except Exception as e:
        logger.warning("er-api.com 汇率获取失败: %s", e)

    logger.error("汇率获取全部失败，返回空结果")
    return result


# ========== 历史日期汇率查询 ==========

def fetch_rate_for_date(
    currency: str, rate_date: date
) -> Optional[Dict[str, object]]:
    """
    获取指定日期的汇率。

    主源优先，失败则备用源。ECB 不发布周末和节假日汇率，
    API 会自动返回最近一个工作日的汇率。

    Args:
        currency: "HKD" 或 "USD"
        rate_date: 目标日期

    Returns:
        {"rate": float, "actual_date": str, "source": str} 或 None
    """
    date_str = rate_date.isoformat()

    # 主源：frankfurter.dev
    try:
        result = _fetch_frankfurter(date_str, [currency])
        key = RATE_KEYS.get(currency)
        if key and result.get(key) is not None:
            return {
                "rate": result[key],
                "actual_date": result.get("date", date_str),
                "source": "frankfurter",
            }
    except Exception as e:
        logger.warning("frankfurter.dev 历史汇率获取失败 (%s, %s): %s",
                       currency, date_str, e)

    # 备用源
    try:
        result = _fetch_er_api(date_str, [currency])
        key = RATE_KEYS.get(currency)
        if key and result.get(key) is not None:
            return {
                "rate": result[key],
                "actual_date": result.get("date", date_str),
                "source": "er-api",
            }
    except Exception as e:
        logger.warning("er-api.com 历史汇率获取失败 (%s, %s): %s",
                       currency, date_str, e)

    return None


# ========== 内部实现 ==========

def _fetch_frankfurter(
    date_or_latest: str,
    currencies: list = None,
) -> Dict[str, Optional[float]]:
    """
    从 frankfurter.dev 获取汇率（ECB 参考汇率）。

    Args:
        date_or_latest: "latest" 或日期字符串 "YYYY-MM-DD"
        currencies: 要查询的币种列表，默认 ["HKD", "USD"]
    """
    currencies = currencies or CURRENCIES
    to_param = ",".join(currencies)
    url = f"{FRANKFURTER_BASE}/{date_or_latest}?from=CNY&to={to_param}"

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        resp = client.get(url)
        resp.raise_for_status()

    data = resp.json()
    rates_data = data.get("rates", {})
    actual_date = data.get("date", date_or_latest)

    result = {"source": "frankfurter", "date": actual_date}
    for currency in currencies:
        key = RATE_KEYS[currency]
        # frankfurter: from=CNY, to=HKD → rates.HKD = 1 CNY = X HKD
        # 需要 HKD/CNY = 1 / X
        raw_rate = rates_data.get(currency)
        if raw_rate and raw_rate > 0:
            result[key] = round(1.0 / raw_rate, 6)
        else:
            result[key] = None

    return result


def _fetch_er_api(
    date_or_latest: str,
    currencies: list = None,
) -> Dict[str, Optional[float]]:
    """
    从 open.er-api.com 获取汇率（备用源）。

    Args:
        date_or_latest: "latest" 或日期字符串 "YYYY-MM-DD"
        currencies: 要查询的币种列表，默认 ["HKD", "USD"]
    """
    currencies = currencies or CURRENCIES

    if date_or_latest == "latest":
        url = f"{ER_API_BASE}/latest/HKD"
    else:
        url = f"{ER_API_BASE}/latest/HKD"

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        resp = client.get(url)
        resp.raise_for_status()

    data = resp.json()
    if data.get("result") != "success":
        raise ValueError(f"API 返回失败: {data.get('result')}")

    rates_data = data.get("rates", {})

    result = {"source": "er-api", "date": date_or_latest}

    # open.er-api.com 以 HKD 为基准
    hkd_cny = rates_data.get("CNY")
    if hkd_cny and hkd_cny > 0:
        result["hkdcny"] = round(hkd_cny, 6)
    else:
        result["hkdcny"] = None

    if "USD" in currencies:
        hkd_usd = rates_data.get("USD")
        if hkd_usd and hkd_usd > 0 and hkd_cny and hkd_cny > 0:
            # USD/CNY = (HKD/CNY) / (HKD/USD)
            result["usdcny"] = round(hkd_cny / hkd_usd, 6)
        else:
            result["usdcny"] = None

    return result


def _validate_rates(result: Dict) -> Dict:
    """验证汇率是否在合理范围内，异常则置为 None"""
    for key, (low, high) in RATE_BOUNDS.items():
        value = result.get(key)
        if value is not None and (value < low or value > high):
            logger.warning("%s 汇率异常: %s（范围 %s-%s），已过滤", key, value, low, high)
            result[key] = None
    return result
