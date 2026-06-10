"""统一文件分析器

合并原 ContractAnalyzer + ReceiptAnalyzer，消除 80% 重复代码。
核心入口：FileAnalyzer.analyze(file_path, file_name, purpose)

支持 purpose:
  - "auto"       : 先分类再提取（默认）
  - "contract"   : 合同提取
  - "receipt"    : 凭证提取
  - "group_chat" : 群聊截图提取
  - "vehicle"    : 车辆照片提取
  - "id_document": 证件提取
  - "general"    : 通用提取

保留原有功能：
  - 合同去重检测（file_hash）
  - Redis 缓存（VL 分析结果）
  - 自动创建付款记录（contract purpose 时）
  - VL 失败 fallback（百炼 → SiliconFlow）
"""
import json
import os
import logging
import shutil
import redis as redis_lib
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.contract import Contract
from app.ai.prompts_v2 import (
    CONTRACT_ANALYSIS_PROMPT,
    RECEIPT_ANALYSIS_PROMPT,
    GROUP_CHAT_ANALYSIS_PROMPT,
    FILE_CLASSIFY_PROMPT,
)
from app.utils.file_utils import calculate_file_hash, resolve_file_path
from app.ai.tools import _get_redis_pool
from app.utils.file_analysis import (
    compress_image,
    detect_image_mime,
    guess_extension,
    make_text_extraction_prompt,
    call_vl_model,
    call_text_model,
    render_pdf_page_to_image,
    extract_pdf_text,
    extract_word_text,
    extract_excel_text,
    is_docx,
    is_xlsx,
    extract_plain_text,
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 归一化 payment_terms
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def normalize_payment_terms(data: dict) -> None:
    """归一化 payment_terms：installment_name→name, due_date→condition 兜底, 缺 name 补序号。"""
    if not isinstance(data, dict):
        return
    terms = data.get("payment_terms")
    if not isinstance(terms, list):
        return
    normalized = []
    for idx, t in enumerate(terms, 1):
        if not isinstance(t, dict):
            normalized.append(t)
            continue
        nt = dict(t)
        if "name" not in nt and "installment_name" in nt:
            nt["name"] = nt.pop("installment_name")
        if not nt.get("name"):
            nt["name"] = f"第 {idx} 期"
        if not nt.get("condition") and nt.get("due_date"):
            nt["condition"] = str(nt["due_date"])
        normalized.append(nt)
    data["payment_terms"] = normalized


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 结果缓存
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_CACHE_PREFIX = "vl:contract:"  # 与 ToolExecutor._cache_key 保持一致，共享缓存
_CACHE_TTL = 1800  # 30 分钟
_memory_cache: dict = {}


def _get_redis_client() -> Optional[redis_lib.Redis]:
    """获取 Redis 客户端（复用 tools.py 的连接池）。"""
    pool = _get_redis_pool()
    if pool is None:
        return None
    try:
        return redis_lib.Redis(connection_pool=pool)
    except Exception:
        return None


def cache_analysis(file_id: str, data: dict, analysis_type: str = "contract") -> None:
    """将分析结果缓存（供 create_contract 等工具复用）。

    仅对 contract 类型写入 file_analyzer 层的全局缓存（key=vl:contract:{file_id}，无 session 维度）；
    receipt/group_chat 等需要 session 隔离的类型由 ToolExecutor._cache_analysis 负责写入，
    避免在此处用 contract 前缀污染其它类型的缓存命名空间。
    """
    if not isinstance(data, dict):
        return
    if analysis_type != "contract":
        return
    redis = _get_redis_client()
    if redis:
        try:
            key = f"{_CACHE_PREFIX}{file_id}"
            redis.setex(key, _CACHE_TTL, json.dumps(data, ensure_ascii=False))
            logger.info("analysis_cache 写入Redis: key=%s, ttl=%ds", key, _CACHE_TTL)
            return
        except Exception:
            logger.warning("cache_analysis Redis 写入失败，降级内存: file_id=%s", file_id)
    _memory_cache[file_id] = data


def get_cached_analysis(file_id: str) -> Optional[dict]:
    """从缓存读取分析结果。"""
    redis = _get_redis_client()
    if redis:
        try:
            key = f"{_CACHE_PREFIX}{file_id}"
            raw = redis.get(key)
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    data = _memory_cache.get(file_id)
    return data if isinstance(data, dict) else None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Prompt 选择
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_PURPOSE_PROMPTS = {
    "contract": CONTRACT_ANALYSIS_PROMPT,
    "receipt": RECEIPT_ANALYSIS_PROMPT,
    "group_chat": GROUP_CHAT_ANALYSIS_PROMPT,
}

# auto 分类返回值 → 内部分析 purpose 映射
# 只接受三种业务类型，其余全部拒绝
_CLASSIFY_TYPE_MAP = {
    "contract": "contract",
    "receipt": "receipt",
    "付款凭证": "receipt",
    "银行转账": "receipt",
    "group_chat": "group_chat",
    "微信群聊": "group_chat",
}

# 拒绝时的提示文案
_UNSUPPORTED_HINT = {
    "vehicle": "车辆照片不属于合同/凭证/群聊，无法自动处理。如需关联到合同，请手动操作。",
    "id_document": "证件照片不属于合同/凭证/群聊，无法自动处理。如需关联到客户，请手动操作。",
    "other": "该文件不属于合同/凭证/群聊，当前系统不支持此类型文件的自动处理。",
    "general": "该文件不属于合同/凭证/群聊，当前系统不支持此类型文件的自动处理。",
}


def _map_classified_type(raw_type: str) -> str:
    """将 VL 分类返回的类型字符串映射为内部 purpose。
    只接受 contract/receipt/group_chat，其余返回 "unsupported"。
    """
    if not raw_type:
        return "unsupported"
    raw_lower = raw_type.lower().strip()
    for key, purpose in _CLASSIFY_TYPE_MAP.items():
        if key in raw_lower:
            return purpose
    return "unsupported"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 核心分析类
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FileAnalyzer:
    """统一文件分析器 — 纯分析逻辑，不涉及 session/持久化

    使用方式：
        result = FileAnalyzer.analyze("/path/to/file", "contract.pdf", purpose="auto")
        # result = {"success": True, "type": "contract", "data": {...}, ...}
    """

    @staticmethod
    def analyze(
        file_path: str,
        file_name: str,
        purpose: str = "auto",
        db: Optional[Session] = None,
        user_id: Optional[int] = None,
        skip_duplicate_check: bool = False,
    ) -> dict:
        """统一分析入口

        Args:
            file_path: 文件绝对路径
            file_name: 原始文件名（用于判断文件类型和缓存 key）
            purpose: 分析目的 (auto/contract/receipt/vehicle/id_document/group_chat/general)
            db: 数据库 session（仅 contract purpose 用于去重检测）
            user_id: 用户 ID（仅用于日志）
            skip_duplicate_check: 跳过去重检测

        Returns:
            {
                "success": bool,
                "type": "contract"|"receipt"|"vehicle"|"id_document"|"group_chat"|"general",
                "data": {...},       # 类型对应的结构化数据
                "file_type": "image"|"pdf"|"word"|"excel"|"text",
                "file_hash": str,
                "confidence": float,
                # contract 专属：
                "duplicate_detected": bool,
                "existing_contract": {...}|None,
            }
        """
        # 读取文件
        try:
            with open(file_path, "rb") as f:
                header = f.read(12)
                f.seek(0)
                file_bytes = f.read()
        except Exception as e:
            return {
                "success": False,
                "error": f"文件读取失败: {e}",
                "type": None,
                "data": None,
                "file_type": None,
                "file_hash": None,
            }

        file_hash = calculate_file_hash(file_bytes)

        # ── 合同去重检测 ──
        if purpose in ("contract", "auto") and db is not None and not skip_duplicate_check:
            existing = db.query(Contract).filter(
                Contract.file_hash == file_hash,
                Contract.is_deleted == False,
            ).first()
            if existing:
                return {
                    "success": True,
                    "type": "contract",
                    "duplicate_detected": True,
                    "data": None,
                    "file_hash": file_hash,
                    "file_type": None,
                    "existing_contract": {
                        "id": existing.id,
                        "contract_number": existing.contract_number,
                        "title": existing.title,
                        "status": existing.status,
                        "total_amount": float(existing.total_amount) if existing.total_amount else 0,
                        "currency": existing.currency,
                        "customer_name": existing.customer.name if existing.customer else None,
                    },
                    "message": "该文件已在系统中存在对应的合同记录",
                }

        # ── 步骤 1：如果是 auto，先做类型分类 ──
        actual_purpose = purpose
        if purpose == "auto":
            actual_purpose = FileAnalyzer._classify_file(file_bytes, file_name, header)

        # ── 拒绝不支持的类型 ──
        if actual_purpose not in _PURPOSE_PROMPTS:
            hint = _UNSUPPORTED_HINT.get(actual_purpose, _UNSUPPORTED_HINT["general"])
            logger.info("file_analyzer: 不支持的文件类型 rejected: purpose=%s file=%s", actual_purpose, file_name)
            return {
                "success": False,
                "type": actual_purpose,
                "error": hint,
                "data": None,
                "file_type": None,
                "file_hash": file_hash,
            }

        # ── 步骤 2：按 purpose 选 prompt，执行分析 ──
        prompt = _PURPOSE_PROMPTS[actual_purpose]
        analysis_result = FileAnalyzer._analyze_content(
            file_path, file_name, file_bytes, header, prompt
        )

        if not analysis_result.get("success"):
            # VL 失败 → fallback 尝试
            analysis_result = FileAnalyzer._fallback_analyze(
                file_path, file_name, file_bytes, header, prompt
            )
            if not analysis_result.get("success"):
                return analysis_result

        structured = analysis_result["data"]
        file_type = analysis_result["file_type"]

        # ── 后处理 ──
        if actual_purpose == "contract":
            normalize_payment_terms(structured)

        confidence = structured.get("confidence", 0.0) if isinstance(structured, dict) else 0.0

        # ── 缓存 ──
        # file_id 从 file_name 提取（去掉扩展名），与 tools.py 保持一致
        # 仅 contract 在此层缓存；receipt/group_chat 由 ToolExecutor 按 session 维度缓存
        file_id = os.path.splitext(os.path.basename(file_path))[0]
        cache_analysis(file_id, structured, actual_purpose)

        result = {
            "success": True,
            "type": actual_purpose,
            "data": structured,
            "file_type": file_type,
            "file_hash": file_hash,
            "confidence": confidence,
            "duplicate_detected": False,
            "existing_contract": None,
        }
        return result

    @staticmethod
    def _classify_file(file_bytes: bytes, file_name: str, header: bytes) -> str:
        """auto 模式：用 VL 或文本模型判断文件类型。

        图片 → VL 做分类（1 次 VL 调用，返回极短结果）
        PDF/文档 → 用文件名 + 文本内容做简单启发式
        """
        mime = detect_image_mime(header)

        if mime:
            # 图片 → VL 分类
            try:
                compressed_bytes, compressed_mime = compress_image(file_bytes, mime)
                classify_result = call_vl_model(compressed_bytes, compressed_mime, FILE_CLASSIFY_PROMPT)
                if isinstance(classify_result, dict):
                    raw_type = classify_result.get("type", "") or classify_result.get("document_type", "")
                    return _map_classified_type(raw_type)
                elif isinstance(classify_result, str):
                    return _map_classified_type(classify_result)
            except Exception as e:
                logger.warning("auto 分类 VL 调用失败: %s, 降级为 unsupported", e)
            return "unsupported"

        # PDF/文档 → 启发式
        if header[:4] == b"%PDF":
            # 看文件名是否有"凭证/收据"等关键词
            name_lower = (file_name or "").lower()
            if any(kw in name_lower for kw in ("凭证", "receipt", "转账", "收据", "付款")):
                return "receipt"
            return "contract"  # PDF 默认当合同

        # Word/Excel → 默认当合同
        return "contract"

    @staticmethod
    def _analyze_content(
        file_path: str, file_name: str, file_bytes: bytes,
        header: bytes, prompt: str,
    ) -> dict:
        """按文件类型选择分析策略（图片/PDF/文档），调用 VL 或文本模型。"""
        mime = detect_image_mime(header)

        if mime:
            # 图片 → VL 模型
            compressed_bytes, compressed_mime = compress_image(file_bytes, mime)
            structured = call_vl_model(compressed_bytes, compressed_mime, prompt)
            return {"success": True, "data": structured, "file_type": "image"}

        if header[:4] == b"%PDF":
            # PDF → 多策略
            full_text = extract_pdf_text(file_path)
            if full_text.strip():
                logger.info("PDF 有文本，使用文本模型解析: text_len=%d", len(full_text))
                text_prompt = make_text_extraction_prompt(prompt)
                structured = call_text_model(full_text, text_prompt)
                if isinstance(structured, dict):
                    structured["full_text"] = full_text
            else:
                logger.info("PDF 无文本（扫描件），渲染为图片走 VL")
                img_bytes = render_pdf_page_to_image(file_path)
                img_bytes, _ = compress_image(img_bytes, "image/png")
                structured = call_vl_model(img_bytes, "image/png", prompt)
            return {"success": True, "data": structured, "file_type": "pdf"}

        # 尝试 Word / Excel / 纯文本
        text_content = ""
        file_type = "document"
        basename = os.path.basename(file_path)

        if file_name.endswith(".docx") or basename.endswith(".docx") or is_docx(file_bytes):
            text_content = extract_word_text(file_path)
            file_type = "word"
        elif file_name.endswith(".xlsx") or basename.endswith(".xlsx") or is_xlsx(file_bytes):
            text_content = extract_excel_text(file_path)
            file_type = "excel"

        # 暴力回退
        if not text_content or not text_content.strip():
            for _extract, _ftype in [
                (extract_word_text, "word"),
                (extract_excel_text, "excel"),
            ]:
                text_content = _extract(file_path)
                if text_content and text_content.strip():
                    file_type = _ftype
                    break
            else:
                text_content = extract_plain_text(file_bytes)
                file_type = "text"

        if not text_content.strip():
            return {
                "success": False,
                "error": "无法提取文件内容，仅支持图片（JPEG/PNG）、PDF、Word（.docx）、Excel（.xlsx）格式",
                "data": None,
                "file_type": None,
            }

        text_prompt = make_text_extraction_prompt(prompt)
        structured = call_text_model(text_content, text_prompt)
        return {"success": True, "data": structured, "file_type": file_type}

    @staticmethod
    def _fallback_analyze(
        file_path: str, file_name: str, file_bytes: bytes,
        header: bytes, prompt: str,
    ) -> dict:
        """主分析失败时的 fallback 策略。

        当前 fallback：返回错误 + 提示用户手动提供关键信息。
        未来可扩展：切换到 VisionModelClient VL 模型。
        """
        return {
            "success": False,
            "error": "文件分析失败，请检查文件格式或手动提供关键信息（如客户名、金额、币种）",
            "data": None,
            "file_type": None,
        }

    @staticmethod
    def copy_to_contract_dir(temp_file_path: str, contract_number: str) -> str:
        """将临时文件复制到合同永久目录。返回相对路径。"""
        with open(temp_file_path, "rb") as f:
            content = f.read()
        ext = guess_extension(content)
        year_month = datetime.now().strftime("%Y/%m")
        target_dir = Path(settings.CONTRACT_UPLOAD_DIR) / year_month
        target_dir.mkdir(parents=True, exist_ok=True)
        target_filename = f"{contract_number}{ext}"
        target_path = target_dir / target_filename
        shutil.copy2(temp_file_path, str(target_path))
        return str(Path(year_month) / target_filename)

    @staticmethod
    def auto_create_payments_from_terms(
        contract: Contract,
        contract_data: dict,
        db: Session,
        user_id: int,
    ) -> list:
        """根据 payment_terms 中标记为已支付的条款，自动创建付款记录。"""
        from app.services.payment_service import PaymentService

        logger.info("自动付款创建开始: contract_id=%d", contract.id)
        if not isinstance(contract_data, dict):
            return []

        payment_terms = contract_data.get("payment_terms", [])
        if not payment_terms:
            return []

        paid_keywords = ["已付", "已缴纳", "付清", "已到账", "已收", "已支付"]
        auto_payments = []

        for idx, term in enumerate(payment_terms, 1):
            is_paid_field = term.get("is_paid")
            condition = (term.get("condition") or "").lower()
            is_paid_by_keywords = any(kw in condition for kw in paid_keywords)
            is_paid_term = (is_paid_field is True) or (is_paid_field is None and is_paid_by_keywords)

            if not is_paid_term:
                continue

            try:
                term_amount = float(term.get("amount", 0))
            except (TypeError, ValueError):
                continue
            if term_amount <= 0:
                continue

            try:
                installment_number = PaymentService.get_next_installment_number(db, contract.id, "income")
                payment = PaymentService.create_payment_with_exchange_rate(
                    db=db,
                    contract_id=contract.id,
                    installment_number=installment_number,
                    currency=contract.currency,
                    amount=Decimal(str(term_amount)),
                    paid_date=contract.signed_date or date.today(),
                    payment_method="unknown",
                    receipt_image_path=None,
                    notes="合同标注已付，待补充凭证",
                    created_by=user_id,
                    type="income",
                    installment_name=term.get("name"),
                )
                auto_payments.append({
                    "payment_id": payment.id,
                    "installment_number": idx,
                    "installment_name": term.get("name"),
                    "amount": term_amount,
                    "currency": contract.currency,
                    "status": payment.status,
                })
            except Exception as e:
                logger.warning("自动创建付款失败: term=%s, error=%s", term.get("name"), e)
                auto_payments.append({
                    "error": str(e),
                    "installment_name": term.get("name"),
                    "amount": term.get("amount"),
                })

        return auto_payments
