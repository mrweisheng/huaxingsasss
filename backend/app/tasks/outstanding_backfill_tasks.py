"""
存量收入记录的剩余尾款（outstanding）回填任务

背景：
    d2eccec 提交后，每次录入收入 LLM 会从「结算状态」原文提取
    outstanding_amount/outstanding_currency 写入对应 payment 行。
    在此之前的存量 income 记录这两个字段为 NULL，前端"剩余尾款"列空缺。

策略（与用户确认）：
    - 范围：每个合同只回填**最新一笔** income（按 paid_date DESC, id DESC）
    - 条件：该笔 outstanding_amount IS NULL 且 notes 非空
    - 提取：调 DeepSeek 非流式 chat completion，强约束 JSON 输出
    - 跳过：notes 无结算信息、LLM 返回 null、解析失败 → 不动该行，warn 日志
    - 币种推断：完全照搬 prompts.py:393-395（明示币种优先，否则 fallback 到本笔 currency）
    - 幂等：WHERE outstanding_amount IS NULL，重复执行结果一致

调度：
    - FastAPI on_startup 触发一次（main.py 通过 .delay() 异步派发，不阻塞启动）
    - Celery beat 每日 05:00 一次（避开 0:30 / 3:00 / 4:00 的已有任务）
"""
import json
import logging
from decimal import Decimal
from typing import Optional

import httpx
from sqlalchemy import text

from app.config import settings
from app.db.session import SessionLocal
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# 专用提示词：只让 LLM 做一件事 — 从结算状态原文提取尾款数字与币种
_EXTRACT_SYSTEM_PROMPT = """你是一个结构化数据提取器。从用户输入的「付款备注原文」中提取剩余尾款数字和币种。

【输入】
- notes: 录入时的备注原文（可能含「结算状态」「已付」「剩多少」等表达，也可能完全无关）
- currency: 本笔收款的币种（CNY 或 HKD），用于币种 fallback

【输出严格 JSON】
{
  "outstanding_amount": 数字 或 null,
  "outstanding_currency": "CNY" 或 "HKD" 或 null,
  "reason": "一句话说明依据，限 30 字内"
}

【提取规则】
1. 备注里写了「剩 X 万 / 還剩 X / 剩余 X / 欠 X」等明确表达当前结算后还差多少 → 提取该数字
   - "剩 6 万" → 60000
   - "剩 6w" → 60000
   - "还差 5000" → 5000
   - "剩 ¥60000" → 60000
2. 备注里写了「已结清 / 結清 / 已收齊 / 全部付清」等表达 → outstanding_amount=0
3. 币种推断：
   - 备注内明示币种（"剩6万人民币" / "剩6万港币" / "¥" / "HK$" / "RMB" / "HKD"）→ 用明示币种
   - 未明示 → outstanding_currency 填传入的 currency 字段
4. 备注完全没有结算相关信息（如只写"已付"、纯日期、空字符串、与剩余无关的话术）→ outstanding_amount 和 outstanding_currency 都返回 null
5. 不要瞎猜，不要用 合同总额 - 已付 自己算 — 必须是用户备注里**明确写出来**的剩余数字
6. 数字必须是普通整数或小数，不能带千分位逗号、不能带货币符号

【几个例子】
- notes="未結清（剩6万，总数21万，已付5+10万）", currency="HKD" → {"outstanding_amount": 60000, "outstanding_currency": "HKD", "reason": "明确剩6万，未注币种用本笔HKD"}
- notes="已结清，总数17万 RMB", currency="CNY" → {"outstanding_amount": 0, "outstanding_currency": "CNY", "reason": "已结清"}
- notes="剩 6 万人民币", currency="HKD" → {"outstanding_amount": 60000, "outstanding_currency": "CNY", "reason": "明示人民币"}
- notes="第二期款项已付", currency="CNY" → {"outstanding_amount": null, "outstanding_currency": null, "reason": "无结算信息"}
- notes="", currency="CNY" → {"outstanding_amount": null, "outstanding_currency": null, "reason": "备注为空"}"""


def _call_llm_extract(notes: str, currency: str) -> Optional[dict]:
    """
    同步调用 DeepSeek 非流式 chat completion，返回解析后的提取结果。

    Returns:
        {"outstanding_amount": Decimal|None, "outstanding_currency": str|None}
        或 None（LLM 调用失败/解析失败）
    """
    user_content = f"notes: {notes!r}\ncurrency: {currency}"
    payload = {
        "model": settings.DEEPSEEK_AGENT_MODEL,
        "messages": [
            {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0,
        "max_tokens": 200,
        "response_format": {"type": "json_object"},
        "stream": False,
        "enable_thinking": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{settings.DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("backfill_llm_call_failed: notes=%r err=%s", notes[:60], exc)
        return None

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("backfill_llm_parse_failed: resp=%r err=%s", data, exc)
        return None

    amount_raw = parsed.get("outstanding_amount")
    currency_raw = parsed.get("outstanding_currency")

    # null 直接跳过（LLM 表态无法提取）
    if amount_raw is None:
        return None

    # 转 Decimal + 校验币种合法
    try:
        amount = Decimal(str(amount_raw))
    except Exception:
        logger.warning("backfill_amount_invalid: raw=%r notes=%r", amount_raw, notes[:60])
        return None

    if currency_raw not in ("CNY", "HKD"):
        # 币种缺失/非法 → fallback 到本笔 currency（兜底，与 prompts.py 规则一致）
        currency_raw = currency if currency in ("CNY", "HKD") else None
        if currency_raw is None:
            return None

    return {
        "outstanding_amount": amount,
        "outstanding_currency": currency_raw,
        "reason": parsed.get("reason", ""),
    }


@celery_app.task(name="app.tasks.outstanding_backfill_tasks.backfill_outstanding", bind=True)
def backfill_outstanding(self):
    """
    扫描存量 income 记录，回填 outstanding_amount / outstanding_currency。

    SQL 策略（PostgreSQL DISTINCT ON）：
        SELECT DISTINCT ON (contract_id) id, contract_id, notes, currency
        FROM payments
        WHERE type='income'
          AND outstanding_amount IS NULL
          AND notes IS NOT NULL AND notes <> ''
        ORDER BY contract_id, paid_date DESC NULLS LAST, id DESC

    对每条候选调 LLM 提取，成功则 UPDATE 该行。
    """
    logger.info("outstanding_backfill_start")

    db = SessionLocal()
    scanned = 0
    updated = 0
    skipped = 0
    failed = 0

    try:
        rows = db.execute(text("""
            SELECT DISTINCT ON (contract_id)
                   id, contract_id, notes, currency
            FROM payments
            WHERE type = 'income'
              AND outstanding_amount IS NULL
              AND notes IS NOT NULL
              AND notes <> ''
            ORDER BY contract_id, paid_date DESC NULLS LAST, id DESC
        """)).fetchall()

        scanned = len(rows)
        logger.info("outstanding_backfill_candidates: count=%d", scanned)

        for row in rows:
            pid, cid, notes, currency = row.id, row.contract_id, row.notes, row.currency
            result = _call_llm_extract(notes, currency or "CNY")

            if result is None:
                skipped += 1
                logger.info(
                    "outstanding_backfill_skip: payment_id=%s contract_id=%s notes=%r",
                    pid, cid, (notes or "")[:80],
                )
                continue

            try:
                db.execute(
                    text("""
                        UPDATE payments
                        SET outstanding_amount = :amount,
                            outstanding_currency = :currency
                        WHERE id = :pid
                          AND outstanding_amount IS NULL
                    """),
                    {
                        "amount": result["outstanding_amount"],
                        "currency": result["outstanding_currency"],
                        "pid": pid,
                    },
                )
                db.commit()
                updated += 1
                logger.info(
                    "outstanding_backfill_update: payment_id=%s contract_id=%s outstanding=%s %s reason=%s",
                    pid, cid,
                    result["outstanding_amount"], result["outstanding_currency"],
                    result.get("reason", ""),
                )
            except Exception as exc:
                db.rollback()
                failed += 1
                logger.warning(
                    "outstanding_backfill_update_failed: payment_id=%s err=%s",
                    pid, exc,
                )

    finally:
        db.close()

    summary = {
        "scanned": scanned,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }
    logger.info("outstanding_backfill_done: %s", summary)
    return summary
