"""
外汇牌价获取服务 - API + LLM 双源方案

架构：
  1. 优先调用广发银行公开 API（稳定、数据格式固定）
  2. API 失败时使用 SiliconFlow LLM 解析银行 HTML（兜底）
  3. LLM 也失败时返回空结果（上层任务会记录错误）

数据来源：
  - 主：广发银行外汇牌价（https://www.cgbchina.com.cn/Channel/17690964）
  - 兜底：中国银行外汇牌价（https://www.boc.cn/sourcedb/whpj/）
"""
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)


# ========== 汇率数据源配置 ==========

CGB_BOC_URL = "https://www.cgbchina.com.cn/Channel/17690964"
BOC_FALLBACK_URL = "https://www.boc.cn/sourcedb/whpj/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


# ========== Prompt 模板 ==========

LLM_SYSTEM_PROMPT = """\
你是一个金融数据提取助手，擅长从银行外汇牌价页面中提取汇率信息。
我会给你一段网页内容，请提取港币(HKD)和美元(USD)兑人民币(CNY)的中行折算价或中间价汇率。
如果找不到某个货币对，返回 null。

返回格式（必须是有效JSON，不要任何其他内容）：
{"hkdcny": 0.92, "usdcny": 7.25}
"""

LLM_USER_PROMPT_TEMPLATE = """\
请从以下银行外汇牌价页面内容中提取 HKD/CNY 和 USD/CNY 的汇率。
只关注"中行折算价"、"中间价"或"现汇买入价/现汇卖出价的平均值"。

---网页内容---
{content}
---结束---

直接返回 JSON，不要解释。"""


# ========== 主函数 ==========

async def fetch_exchange_rates() -> Dict[str, Optional[float]]:
    """
    获取 HKD/CNY 和 USD/CNY 汇率。

    执行顺序：
    1. 优先从广发银行 API 获取
    2. 失败则用 LLM 解析银行 HTML
    3. 都失败返回空结果

    Returns:
        {"hkdcny": float or None, "usdcny": float or None, "source": str, "date": str}
    """
    result = {
        "hkdcny": None,
        "usdcny": None,
        "source": None,
        "date": None,
    }

    # 方式1：广发银行（稳定）
    try:
        rates = await _fetch_from_cgb()
        if rates["hkdcny"] is not None and rates["usdcny"] is not None:
            result.update(rates)
            logger.info("汇率获取成功（广发银行）: HKD/CNY=%s, USD/CNY=%s",
                       rates["hkdcny"], rates["usdcny"])
            return result
    except Exception as e:
        logger.warning("广发银行汇率获取失败: %s，尝试 LLM 兜底...", e)

    # 方式2：LLM 解析 HTML（兜底）
    try:
        rates = await _fetch_from_llm()
        if rates["hkdcny"] is not None or rates["usdcny"] is not None:
            result.update(rates)
            logger.info("汇率获取成功（LLM兜底）: HKD/CNY=%s, USD/CNY=%s",
                       rates["hkdcny"], rates["usdcny"])
            return result
    except Exception as e:
        logger.warning("LLM 汇率提取失败: %s", e)

    # 全部失败
    logger.error("汇率获取全部失败，返回空结果")
    return result


async def _fetch_from_cgb() -> Dict[str, Optional[float]]:
    """
    从广发银行外汇牌价页面获取汇率。

    广发银行页面结构简单，汇率直接嵌入 HTML 表格中。
    页面URL: https://www.cgbchina.com.cn/Channel/17690964
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(CGB_BOC_URL, headers=HEADERS)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    rates = {"hkdcny": None, "usdcny": None, "source": "cgb", "date": None}

    # 查找表格
    table = soup.find("table")
    if not table:
        raise ValueError("未找到汇率表格")

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        cell_texts = [cell.get_text(strip=True) for cell in cells]

        # 解析货币代码（第二列通常是币种简称）
        currency_code = cell_texts[1] if len(cell_texts) > 1 else ""

        # 跳过表头或无效行
        if "Currency Code" in currency_code or len(currency_code) > 5:
            continue

        # 解析汇率（第三列是中间价/Middle Rate）
        try:
            rate_str = cell_texts[3] if len(cell_texts) > 3 else ""
            if not rate_str or rate_str == "-":
                continue

            rate_value = float(rate_str)

            # 根据货币代码匹配
            if "HKD" in currency_code or "港元" in cell_texts[0]:
                rates["hkdcny"] = rate_value
            elif "USD" in currency_code or "美元" in cell_texts[0]:
                rates["usdcny"] = rate_value

        except (ValueError, IndexError):
            continue

    # 提取日期（页面发布时间）
    date_match = re.search(r"发布时间[为：:]\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", resp.text)
    if date_match:
        rates["date"] = date_match.group(1)

    # 验证数据合理性
    if rates["hkdcny"] is not None and (rates["hkdcny"] < 0.5 or rates["hkdcny"] > 2):
        logger.warning("HKD/CNY 汇率异常: %s，已过滤", rates["hkdcny"])
        rates["hkdcny"] = None

    if rates["usdcny"] is not None and (rates["usdcny"] < 5 or rates["usdcny"] > 10):
        logger.warning("USD/CNY 汇率异常: %s，已过滤", rates["usdcny"])
        rates["usdcny"] = None

    return rates


async def _fetch_from_llm() -> Dict[str, Optional[float]]:
    """
    使用 LLM 从银行网页提取汇率（兜底方案）。

    直接把原始 HTML 丢给 LLM，让它自己解析页面结构。
    不做预处理，不依赖页面结构变化。
    """
    # 获取中国银行页面 HTML
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(BOC_FALLBACK_URL, headers=HEADERS)
        resp.raise_for_status()

    # 限制内容长度（LLM 输入有限制）
    html_content = resp.text[:50000]

    # 构造 LLM 请求
    api_key = settings.SILICONFLOW_API_KEY
    base_url = settings.SILICONFLOW_BASE_URL
    text_model = settings.SILICONFLOW_TEXT_MODEL

    user_prompt = LLM_USER_PROMPT_TEMPLATE.format(content=html_content)

    payload = {
        "model": text_model,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 256,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()

    raw = resp.json()
    llm_response = raw.get("choices", [{}])[0].get("message", {}).get("content", "")

    # 解析 JSON
    json_str = _extract_json_from_text(llm_response)
    if json_str is None:
        raise ValueError("LLM 未返回有效 JSON")

    parsed = json.loads(json_str)

    # 验证和转换
    result = {
        "hkdcny": None,
        "usdcny": None,
        "source": "llm/boc",
        "date": None,
    }

    for key in ("hkdcny", "usdcny"):
        value = parsed.get(key)
        if value is None:
            continue
        try:
            rate = Decimal(str(value))
            if rate <= 0:
                raise ValueError(f"汇率值 {rate} 不是正数")
            divisor = 100 if rate > 10 else 1
            rate = rate / divisor
            result[key] = float(rate)
        except (InvalidOperation, ValueError) as e:
            logger.warning("汇率值无效: %s - %s", value, e)

    return result


def _extract_json_from_text(text: str) -> Optional[str]:
    """
    从 LLM 响应中提取 JSON 字符串。
    """
    # 匹配 ```json ... ``` 或 ``` ... ```
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```", text)
    if match:
        candidate = match.group(1).strip()
        if "{" in candidate and "}" in candidate:
            return candidate

    # 找到第一个 { 到最后一个 }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        open_count = candidate.count("{")
        close_count = candidate.count("}")
        if open_count == close_count and open_count >= 1:
            return candidate

    return None