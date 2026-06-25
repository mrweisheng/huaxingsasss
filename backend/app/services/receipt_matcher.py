"""凭证识别结果 vs 合同/付款计划 三态对比器

供 Agent 对话流的 analyze_receipt 工具同步前置使用：
  - ok            : 所有关键字段命中（金额/币种/付款方），可直接落库
  - soft_mismatch : 凭证轻微不符（金额超容差/币种不同/客户名相似但不完全匹配），允许放行
  - hard_conflict : 凭证客户与合同客户完全不相干，禁止录入，工具入口硬挡

设计原则：
- 确定性代码判定，不让 LLM 自由心证（CLAUDE.md「数据完整性边界放代码层」铁律）
- 与 receipt_verification_tasks._amount_matches / _name_matches 口径一致（金额±2%、名称包含或归一化等值）
- aliases 命中收款账户 → 直接视为客户匹配（最高优先级，零拆词零误判）
"""
import re
import logging
from decimal import Decimal, InvalidOperation
from datetime import date, timedelta
from typing import Optional

from app.models.contract import Contract
from app.models.customer import Customer
from app.models.payment_account import PaymentAccount

logger = logging.getLogger(__name__)


# ── 容差常量（与异步校验任务对齐） ──
AMOUNT_TOLERANCE = Decimal("0.02")    # ±2%
DATE_TOLERANCE_DAYS = 1                # ±1 天


def _to_decimal(val) -> Optional[Decimal]:
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _normalize_name(s: str) -> str:
    """去除空格、括号、连字符、点号，便于"胡少棟（XX公司）"和"胡少棟"等价比较。"""
    return re.sub(r"[\s（）()·\-_、,，]", "", s or "")


def _to_simplified(s: str) -> str:
    """繁→简归一。失败/空值原样返回。"""
    if not s:
        return ""
    try:
        from app.core.chinese import _t2s
        return _t2s.convert(s)
    except Exception:
        return s


def _name_contains(a: str, b: str) -> bool:
    """名称包含/归一化等值判定，沿用异步校验任务的口径。"""
    if not a or not b:
        return False
    al = a.strip().lower()
    bl = b.strip().lower()
    if not al or not bl:
        return False
    if al in bl or bl in al:
        return True
    if _normalize_name(al) == _normalize_name(bl):
        return True
    # 简繁归一后再比一次
    as_ = _to_simplified(al)
    bs_ = _to_simplified(bl)
    if as_ in bs_ or bs_ in as_:
        return True
    if _normalize_name(as_) == _normalize_name(bs_):
        return True
    return False


def _amount_matches(expected: Optional[Decimal], extracted: Optional[Decimal]) -> bool:
    """金额比对：允许 ±2% 偏差，兼容手填/识别微小误差。"""
    if expected is None or extracted is None:
        return False
    if expected == 0:
        return extracted == 0
    return abs(extracted - expected) / abs(expected) <= AMOUNT_TOLERANCE


def _date_matches(expected: Optional[date], extracted: Optional[date]) -> bool:
    """日期比对：允许 ±1 天偏差。"""
    if expected is None or extracted is None:
        return True   # 任一缺失不以此判失败
    return abs((extracted - expected).days) <= DATE_TOLERANCE_DAYS


def _parse_date(val) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def _is_hard_conflict_name(
    extracted_payer: str,
    customer_name: str,
    wechat_group: str,
    payment_account: Optional[PaymentAccount],
) -> bool:
    """判断「凭证付款方与合同客户完全不相干」（hard_conflict 入口判定）。

    规则（全部为 True 才算硬冲突，宁松勿严，避免误杀合法变体）：
      1. _name_contains 不通过（既不包含也不归一化等值）
      2. 不命中收款账户 aliases（admin 显式登记的别名）
      3. 不在合同微信群名里出现（"张老板群"含"张"，与合同客户"张三"虽不同字也算软冲突）
      4. 简繁归一后字符集无任何重叠（连一个共同字符都没有）

    缺失字段保守判 False（不算硬冲突），交由 soft_mismatch 处理。
    """
    if not extracted_payer or not customer_name:
        return False

    # 规则 1
    if _name_contains(extracted_payer, customer_name):
        return False

    # 规则 2：aliases 命中
    if payment_account is not None:
        aliases = (payment_account.extra_info or {}).get("aliases") or []
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str) and _name_contains(extracted_payer, alias):
                    return False

    # 规则 3：微信群名包含付款方任意一段
    if wechat_group:
        if _name_contains(extracted_payer, wechat_group):
            return False

    # 规则 4：字符集重叠（简繁归一后）
    a = _normalize_name(_to_simplified(extracted_payer))
    b = _normalize_name(_to_simplified(customer_name))
    # 单字符姓氏与全名也可能重叠；至少 1 个共同字符就放它过
    if set(a) & set(b):
        return False

    return True


def _build_diff(
    field: str, expected, got, severity: str = "soft",
) -> dict:
    return {
        "field": field,
        "expected": expected,
        "got": got,
        "severity": severity,
    }


def _strip_date_prefix(s: str) -> str:
    """去掉群名开头的日期前缀，如"6月20日"/"2025年6月13日"/"6/20"等。

    日期是群名的辅助标识，业务主体在日期后面。比较时去掉日期能更精确地
    匹配业务主体（人名+车型）。
    """
    if not s:
        return ""
    # 匹配开头的：YYYY年? + M月D日? / M月D日 / M/D / YYYY/M/D 等
    pattern = r"^[\s\d年月日/.\-]+"
    return re.sub(pattern, "", s).strip()


def match_wechat_group(extracted_group: str, contract_group: str) -> dict:
    """微信群名称三态模糊匹配。

    用于「付款信息文字截图」与合同的群名称一致性校验。规则（从严到宽）：
      strict   ：完全相等（去首尾空格）/ 去标点空格后归一化等值
      loose    ：去日期前缀后等值 / 双向包含（业务主体部分）
      missing  ：任一方缺失
      conflict ：以上都不命中

    设计要点：群名一般形如"6月20日陈世勇40系白外黑内埃尔法"，前缀是日期，
    业务主体在后。比较时优先剥离日期前缀，再做主体匹配。

    Args:
        extracted_group: 从付款信息提取的群名称
        contract_group: 合同关联的群名称

    Returns:
        {"status": "strict|loose|missing|conflict", "reason": "..."}
    """
    a_raw = (extracted_group or "").strip()
    b_raw = (contract_group or "").strip()
    if not a_raw or not b_raw:
        return {"status": "missing", "reason": "群名称缺失，无法校验"}

    # strict 1：完全相等
    if a_raw == b_raw:
        return {"status": "strict", "reason": "群名称完全一致"}

    # strict 2：去空格标点后等值
    a_norm = _normalize_name(a_raw)
    b_norm = _normalize_name(b_raw)
    if a_norm == b_norm:
        return {"status": "strict", "reason": "群名称去空格标点后一致"}

    # strict 3：简繁归一后等值
    a_s = _normalize_name(_to_simplified(a_raw))
    b_s = _normalize_name(_to_simplified(b_raw))
    if a_s == b_s:
        return {"status": "strict", "reason": "群名称简繁归一后一致"}

    # 去日期前缀后再比较（业务主体匹配）
    a_body = _normalize_name(_to_simplified(_strip_date_prefix(a_raw)))
    b_body = _normalize_name(_to_simplified(_strip_date_prefix(b_raw)))

    # strict 4：业务主体完全相等（仅日期差异）
    if a_body and b_body and a_body == b_body:
        return {"status": "strict", "reason": "群名称业务主体一致（仅日期差异）"}

    # loose 1：双向包含（原始）
    if a_norm in b_norm or b_norm in a_norm:
        return {"status": "loose", "reason": "群名称包含匹配"}
    if a_s in b_s or b_s in a_s:
        return {"status": "loose", "reason": "群名称简繁归一后包含匹配"}

    # loose 2：业务主体双向包含（只要主体明显重叠）
    if a_body and b_body and (a_body in b_body or b_body in a_body):
        return {"status": "loose", "reason": "群名称业务主体包含匹配"}

    return {"status": "conflict", "reason": "群名称完全不同"}


def match_receipt(
    *,
    extracted: dict,
    contract: Contract,
    customer: Customer,
    payment_account: Optional[PaymentAccount] = None,
    expected_payment_term: Optional[dict] = None,
    payment_type: str = "income",
) -> dict:
    """三态对比凭证与合同/付款计划。

    Args:
        extracted: VL 提取结果，至少包含 {amount, currency, payer_name?, transaction_date?, document_type?}
        contract: 合同 ORM 对象
        customer: 合同关联客户 ORM 对象
        payment_account: 凭证 hint 命中的收款账户（用于 aliases 判定，可为 None）
        expected_payment_term: 选定的付款计划项 {amount, currency, name}（可为 None，跳过 term 比对）
        payment_type: income / expense（支出弱校验：客户匹配不参与硬冲突判定）

    Returns:
        {
            "match_status": "ok" | "soft_mismatch" | "hard_conflict",
            "diff_fields": [{field, expected, got, severity}, ...],
            "expected": {...},   # 期望快照
            "extracted_norm": {...},  # 归一化后的提取快照（金额转 Decimal、日期 ISO 等）
            "confidence": float,
            "reason": str,
        }
    """
    ext_amount = _to_decimal(extracted.get("amount"))
    ext_currency = (extracted.get("currency") or "").upper() or None
    ext_payer = (extracted.get("payer_name") or "").strip() or None
    ext_payee = (extracted.get("payee_name") or "").strip() or None
    ext_date = _parse_date(extracted.get("transaction_date"))
    confidence = float(extracted.get("confidence") or 0.0)

    # 期望值：优先用付款计划项；否则用合同主币种 + 总额（仅用于币种比对，金额留空）
    if expected_payment_term and isinstance(expected_payment_term, dict):
        exp_amount = _to_decimal(expected_payment_term.get("amount"))
        exp_currency = (expected_payment_term.get("currency") or contract.currency or "CNY").upper()
        exp_term_name = expected_payment_term.get("name") or ""
    else:
        exp_amount = None
        exp_currency = (contract.currency or "CNY").upper()
        exp_term_name = ""

    exp_customer = customer.name if customer else ""
    exp_wechat_group = contract.wechat_group or ""

    diffs: list[dict] = []

    # ── 1. 客户名 / 付款方 对比（仅 income 走 hard_conflict） ──
    payer_severity_hard = False
    if payment_type == "income":
        # 收入：凭证付款方 = 合同客户
        is_hard = _is_hard_conflict_name(
            ext_payer or "", exp_customer, exp_wechat_group, payment_account,
        )
        if is_hard:
            payer_severity_hard = True
            diffs.append(_build_diff(
                "payer_name", exp_customer, ext_payer, "hard",
            ))
        elif ext_payer and exp_customer and not _name_contains(ext_payer, exp_customer):
            # 收款账户 aliases 命中？
            alias_hit = False
            if payment_account is not None:
                aliases = (payment_account.extra_info or {}).get("aliases") or []
                if isinstance(aliases, list):
                    for alias in aliases:
                        if isinstance(alias, str) and _name_contains(ext_payer, alias):
                            alias_hit = True
                            break
            if not alias_hit:
                diffs.append(_build_diff("payer_name", exp_customer, ext_payer, "soft"))
    else:
        # 支出：弱校验。仅当凭证收款方与表单 payee_name 完全无关时提示 soft
        # （此函数 input 不含 payee_name 用户输入，调用方自己加 diff，此处不处理）
        pass

    # ── 2. 金额对比 ──
    if exp_amount is not None and ext_amount is not None:
        if not _amount_matches(exp_amount, ext_amount):
            diffs.append(_build_diff(
                "amount",
                float(exp_amount), float(ext_amount),
                "soft",
            ))

    # ── 3. 币种对比 ──
    if exp_currency and ext_currency and exp_currency != ext_currency:
        diffs.append(_build_diff("currency", exp_currency, ext_currency, "soft"))

    # ── 4. 置信度低 → 标记 soft ──
    if confidence and confidence < 0.6:
        diffs.append(_build_diff("confidence", ">=0.6", confidence, "soft"))

    # ── 三态判定 ──
    if payer_severity_hard:
        match_status = "hard_conflict"
        reason = "凭证付款方与合同客户完全不一致，禁止录入"
    elif not diffs:
        match_status = "ok"
        reason = "凭证与合同关键字段全部匹配"
    else:
        match_status = "soft_mismatch"
        reason = "、".join(d["field"] for d in diffs) + " 不一致或需复核"

    expected_snapshot = {
        "customer_name": exp_customer,
        "wechat_group": exp_wechat_group,
        "amount": float(exp_amount) if exp_amount is not None else None,
        "currency": exp_currency,
        "term_name": exp_term_name,
    }
    extracted_norm = {
        "amount": float(ext_amount) if ext_amount is not None else None,
        "currency": ext_currency,
        "payer_name": ext_payer,
        "payee_name": ext_payee,
        "transaction_date": ext_date.isoformat() if ext_date else None,
        "document_type": extracted.get("document_type"),
        "confidence": confidence,
    }

    logger.info(
        "ReceiptMatcher: contract_id=%s, type=%s, status=%s, diffs=%d, reason=%s",
        getattr(contract, "id", None), payment_type, match_status, len(diffs), reason,
    )

    return {
        "match_status": match_status,
        "diff_fields": diffs,
        "expected": expected_snapshot,
        "extracted_norm": extracted_norm,
        "confidence": confidence,
        "reason": reason,
    }


def pick_payment_term(
    contract: Contract,
    extracted_amount: Optional[Decimal],
    extracted_currency: Optional[str],
) -> Optional[dict]:
    """从合同 payment_terms 中按金额/币种命中一期，返回 {name, amount, currency}。

    匹配规则：
      1. 币种相同
      2. |term_amount - extracted_amount| / term_amount < 1% 或 < 100
      3. 多期同金额命中第一个

    匹配失败返回 None，调用方按合同主币种比对。
    """
    if not contract or not extracted_amount or not extracted_currency:
        return None
    contract_data = getattr(contract, "contract_data", None) or {}
    if not isinstance(contract_data, dict):
        return None
    terms = contract_data.get("payment_terms") or []
    if not isinstance(terms, list):
        return None
    target_amount = _to_decimal(extracted_amount)
    target_currency = extracted_currency.upper()
    if target_amount is None:
        return None
    for term in terms:
        if not isinstance(term, dict):
            continue
        term_currency = (term.get("currency") or contract.currency or "CNY").upper()
        if term_currency != target_currency:
            continue
        term_amount = _to_decimal(term.get("amount"))
        if term_amount is None or term_amount <= 0:
            continue
        diff = abs(term_amount - target_amount)
        if diff < 100 or diff / term_amount < Decimal("0.01"):
            return {
                "name": term.get("name") or "",
                "amount": float(term_amount),
                "currency": term_currency,
            }
    return None
