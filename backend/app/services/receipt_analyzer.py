"""
凭证分析器
从 tools.py 提取的凭证 VL 分析逻辑，供 Agent 工具和页面端点复用。
职责：文件类型检测 → 图片压缩 → VL/文本模型调用 → 结构化输出 + warnings 注入。
不涉及 Redis 缓存、session 上下文、文件持久化。
"""
import os
import logging

from app.ai.prompts import RECEIPT_ANALYSIS_PROMPT
from app.utils.file_analysis import (
    compress_image,
    detect_image_mime,
    call_vl_model,
    call_text_model,
    render_pdf_page_to_image,
    extract_pdf_text,
    extract_word_text,
    extract_excel_text,
    is_docx,
    is_xlsx,
    extract_plain_text,
    make_text_extraction_prompt,
)

logger = logging.getLogger(__name__)


class ReceiptAnalyzer:
    """凭证文件分析器——纯分析逻辑，不涉及缓存/session/持久化"""

    @staticmethod
    def _inject_receipt_warnings(structured: dict) -> None:
        """凭证分析结果：检测币种/交易日期缺失，注入 _warnings。"""
        warnings = []
        if not structured.get("currency"):
            warnings.append("币种未识别")
        if not structured.get("transaction_date"):
            warnings.append("交易日期未识别")
        if warnings:
            structured["_warnings"] = warnings

    @staticmethod
    def analyze_from_file(file_path: str, file_name: str) -> dict:
        """从文件路径分析凭证（图片/PDF/Word/Excel）。

        Args:
            file_path: 已保存在 TEMP_UPLOAD_DIR 中的文件绝对路径。
            file_name: 原始文件名（用于判断文件类型）。

        Returns:
            {
                "success": True,
                "data": {
                    "amount", "currency", "transaction_date", "payer_name",
                    "payee_name", "payment_method", "confidence",
                    "_warnings": [...]  # 币种/日期缺失时自动注入
                },
                "file_type": "image" | "pdf" | "document"
            }
        """
        # 读取文件
        with open(file_path, "rb") as f:
            header = f.read(12)
            f.seek(0)
            file_bytes = f.read()

        # 判断文件类型并分析
        mime = detect_image_mime(header)

        if mime:
            # 图片 → VL 模型
            compressed_bytes, compressed_mime = compress_image(file_bytes, mime)
            structured = call_vl_model(compressed_bytes, compressed_mime, RECEIPT_ANALYSIS_PROMPT)
            file_type = "image"
        elif header[:4] == b"%PDF":
            # PDF → 多策略
            full_text = extract_pdf_text(file_path)
            if full_text.strip():
                logger.info("PDF 有文本，使用文本模型解析: text_len=%d", len(full_text))
                prompt = make_text_extraction_prompt(RECEIPT_ANALYSIS_PROMPT)
                structured = call_text_model(full_text, prompt)
            else:
                logger.info("PDF 无文本（扫描件），渲染为图片走 VL")
                img_bytes = render_pdf_page_to_image(file_path)
                img_bytes, _ = compress_image(img_bytes, "image/png")
                structured = call_vl_model(img_bytes, "image/png", RECEIPT_ANALYSIS_PROMPT)
            file_type = "pdf"
        else:
            # 尝试 Word / Excel / 纯文本
            text_content = ""
            file_type = "document"
            basename = os.path.basename(file_path)
            if file_name.endswith(".docx") or basename.endswith(".docx") or is_docx(file_bytes):
                text_content = extract_word_text(file_path)
            elif file_name.endswith(".xlsx") or basename.endswith(".xlsx") or is_xlsx(file_bytes):
                text_content = extract_excel_text(file_path)

            # 检测未命中或提取为空 → 暴力回退
            if not text_content or not text_content.strip():
                for _extract in (extract_word_text, extract_excel_text):
                    text_content = _extract(file_path)
                    if text_content and text_content.strip():
                        break
                else:
                    text_content = extract_plain_text(file_bytes)

            if not text_content.strip():
                return {
                    "success": False,
                    "error": "无法提取文件内容，仅支持图片（JPEG/PNG）、PDF、Word（.docx）、Excel（.xlsx）格式",
                    "file_type": None,
                    "data": None,
                }

            prompt = make_text_extraction_prompt(RECEIPT_ANALYSIS_PROMPT)
            structured = call_text_model(text_content, prompt)

        # 注入 warnings
        ReceiptAnalyzer._inject_receipt_warnings(structured)

        return {
            "success": True,
            "data": structured,
            "file_type": file_type,
        }
