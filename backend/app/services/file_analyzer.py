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
   - VL 失败 fallback
"""
import json
import os
import logging
import shutil
import redis as redis_lib
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.contract import Contract
from app.ai.prompts import (
    CONTRACT_ANALYSIS_PROMPT,
    RECEIPT_ANALYSIS_PROMPT,
    GROUP_CHAT_ANALYSIS_PROMPT,
    FILE_CLASSIFY_PROMPT,
    PAYMENT_TEXT_EXTRACT_PROMPT,
)
from app.utils.file_utils import calculate_file_hash, resolve_file_path
from app.ai.tool_executor_base import _get_redis_pool
from app.utils.file_analysis import (
    compress_image,
    detect_image_mime,
    guess_extension,
    normalize_payment_terms,
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
    "payment_info": PAYMENT_TEXT_EXTRACT_PROMPT,   # 付款信息文字截图（聊天记录手敲的转账描述）
}

# auto 分类返回值 → 内部分析 purpose 映射
# 接受四种业务类型，其余全部拒绝
_CLASSIFY_TYPE_MAP = {
    "contract": "contract",
    "receipt": "receipt",
    "付款凭证": "receipt",
    "银行转账": "receipt",
    "group_chat": "group_chat",
    "微信群聊": "group_chat",
    "payment_info": "payment_info",
    "付款信息": "payment_info",
    "转账记录": "payment_info",
    "转账描述": "payment_info",
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
    只接受 contract/receipt/group_chat/payment_info，其余返回 "unsupported"。
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
        contract_id: Optional[int] = None,
    ) -> dict:
        """统一分析入口

        Args:
            file_path: 文件绝对路径
            file_name: 原始文件名（用于判断文件类型和缓存 key）
            purpose: 分析目的 (auto/contract/receipt/vehicle/id_document/group_chat/general)
            db: 数据库 session（contract purpose 用于去重检测；receipt 在有 contract_id 时用于凭证去重）
            user_id: 用户 ID（仅用于日志）
            skip_duplicate_check: 跳过去重检测
            contract_id: 合同 ID（receipt 去重时限定合同范围；合同去重不使用此参数）

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

        # ── 凭证去重检测（VL 分析前拦截，省时省钱）──
        # 仅当识别为 receipt 且有合同上下文时检查（凭证去重 scope = 合同内）
        if actual_purpose == "receipt" and db is not None and contract_id and not skip_duplicate_check:
            from app.models.payment import Payment
            existing = db.query(Payment).filter(
                Payment.contract_id == contract_id,
                Payment.receipt_file_hash == file_hash,
                Payment.is_deleted == False,
            ).first()
            if existing:
                logger.info(
                    "file_analyzer: 凭证去重命中(VL前拦截): contract_id=%s, existing_payment_id=%s, hash=%s",
                    contract_id, existing.id, file_hash[:12],
                )
                return {
                    "success": True,
                    "type": "receipt",
                    "duplicate_detected": True,
                    "data": None,
                    "file_hash": file_hash,
                    "file_type": None,
                    "existing_payment": {
                        "id": existing.id,
                        "type": existing.type,
                        "amount": float(existing.amount) if existing.amount else 0,
                        "currency": existing.currency,
                        "status": existing.status,
                        "paid_date": str(existing.paid_date) if existing.paid_date else None,
                        "payee_name": existing.payee_name,
                        "description": existing.description,
                    },
                    "message": "该凭证已在此合同下录入过",
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
            # 图片 → VL 分类（前端已压缩，直接传）
            try:
                classify_result = call_vl_model(file_bytes, mime, FILE_CLASSIFY_PROMPT)
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
            # 图片 → VL 模型（前端已压缩，直接传）
            structured = call_vl_model(file_bytes, mime, prompt)
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
