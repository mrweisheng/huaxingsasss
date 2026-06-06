#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3 vs qwen3-vl-flash 多模态速度 / 效果对比脚本

流程:
  1. 读取图片 → Pillow 压缩到短边 1600px、JPEG 质量 85%
  2. 分别调用 M3（MiniMax）和 qwen3-vl-flash（DashScope），同一个压缩后的图
  3. 同一个 prompt，强制 JSON 输出
  4. 各自统计：HTTP 连接 / TTFT / 流时长 / 总耗时 / tokens / JSON 解析
  5. 输出对比表 + 双方原始输出

依赖:
  pip install Pillow   # 图片压缩
  解析 .env 走自己实现，不依赖 python-dotenv

用法:
  # 默认跑 牌.jpg
  python m3_test.py

  # 指定图片
  python m3_test.py --image "D:\\CODE PROJECT\\huaxingsasss\\车.jpg"

  # 跳过图片压缩（用原图）
  python m3_test.py --no-compress

  # 自定义压缩参数
  python m3_test.py --max-edge 1024 --jpeg-quality 70

  # 跳过 .env 自动发现（手动指定 key）
  python m3_test.py --env-file "" --m3-key sk-cp-xxx --dashscope-key sk-xxx

  # 也支持环境变量覆盖
  set M3_API_KEY=sk-cp-xxx
  set DASHSCOPE_API_KEY=sk-xxx
  python m3_test.py

⚠️ 本地开发测试脚本，**不要 commit**（脚本里硬编码了 M3 的 key，调试用）。
"""
import argparse
import base64
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

# ── 依赖：Pillow（仅用于图片压缩） ───────────────────────────────────────────────
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── 默认配置 ─────────────────────────────────────────────────────────────────────
DEFAULT_M3_KEY = "sk-cp-qBGVa4tWBn7-tpZhYuPMbA37qS8ZE0xBZYGz2O9vJwWkwF4AsLbKlwAak3P--ql-cO63V9swLv9BeU5Dg07GqlyS6obrxTrG_-q5ARiyS2_vf-iRCqDr_mg"
DEFAULT_M3_BASE_URL = "https://api.minimaxi.com/v1"
DEFAULT_M3_MODEL = "MiniMax-M3"
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_DASHSCOPE_VL_MODEL = "qwen3-vl-flash"
DEFAULT_IMAGE = "牌.jpg"

DEFAULT_ENV_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "backend", ".env"
)

# ── 提示词：与项目现有合同/凭证提取 prompt 风格一致 ─────────────────────────────
PROMPT = """你是一个专业的信息提取助手。请仔细分析这张图片，提取所有可见的关键信息并以**严格的 JSON 格式**返回。

严格要求：
1. 只返回纯 JSON，不要任何 markdown 包裹（不要 ```json```），不要任何前言/解释/注释
2. 先识别图片类型并放入 type 字段："车牌" / "合同" / "凭证" / "聊天截图" / "其他"
3. 根据类型提取对应字段，无法识别时填 null：
   - 车牌：plate_number, vehicle_model, color, plate_color（蓝牌/黄牌等）
   - 合同：contract_number, title, party_a, party_b, total_amount(数字), currency(CNY/HKD/USD), signed_date(YYYY-MM-DD), payment_terms
   - 凭证：payer_name, payee_name, amount(数字), currency, transaction_date(YYYY-MM-DD), transaction_id, payment_method
   - 聊天截图：group_name, members, date, summary
   - 其他：description（一句话中文描述）
4. 必须包含 extracted_text 字段：图片中**所有可见文字**的逐字转录，保留原文繁体不转简体
5. 必须包含 confidence 字段：0-1 数字，代表整体识别置信度
6. 金额统一为数字类型，日期统一为 YYYY-MM-DD

返回示例：
{"type":"车牌","plate_number":"粤Z7N80港","vehicle_model":null,"color":null,"plate_color":null,"extracted_text":"粤Z7N80港","confidence":0.95}
"""


# ── 工具函数 ─────────────────────────────────────────────────────────────────────
def now() -> float:
    return time.perf_counter()


def log(stage: str, t_start: float, t_end: float, **extra: Any) -> None:
    elapsed_ms = (t_end - t_start) * 1000
    extra_str = "  ".join(f"{k}={v}" for k, v in extra.items())
    print(f"[{t_end:>9.3f}s] {stage:<24} {elapsed_ms:>8.1f}ms  {extra_str}", flush=True)


def find_image(image_path: str) -> str:
    candidates = [
        os.path.abspath(image_path),
        image_path,
        os.path.join(os.getcwd(), image_path),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", image_path),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", image_path),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return ""


def parse_env_file(path: str) -> Dict[str, str]:
    """极简 .env 解析：忽略注释/空行，支持引号。"""
    result: Dict[str, str] = {}
    if not path or not os.path.isfile(path):
        return result
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$", line, re.IGNORECASE)
                if not m:
                    continue
                key, value = m.group(1), m.group(2)
                # 去掉行内注释
                if " #" in value:
                    value = value.split(" #", 1)[0].strip()
                # 去掉包裹引号
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                result[key] = value
    except Exception as e:
        print(f"⚠️ 解析 .env 失败: {e}")
    return result


def compress_image(image_bytes: bytes, max_edge: int = 1600, quality: int = 85) -> Tuple[bytes, int, int, int]:
    """用 Pillow 缩到短边 ≤ max_edge，返回 (jpeg_bytes, orig_w, orig_h, new_w, new_h)。

    没有 Pillow 时返回原图（标注 fallback）。
    """
    if not HAS_PIL:
        return image_bytes, 0, 0, 0  # 无法识别尺寸
    img = Image.open(BytesIO(image_bytes))
    orig_w, orig_h = img.size
    # 转换到 RGB（去 alpha）
    if img.mode != "RGB":
        img = img.convert("RGB")
    # 计算缩放
    w, h = img.size
    if max(w, h) > max_edge:
        scale = max_edge / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    else:
        new_w, new_h = w, h
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), orig_w, orig_h, new_w, new_h


def call_chat_completions_stream(
    api_key: str,
    base_url: str,
    model: str,
    image_b64: str,
    prompt: str,
    label: str,
    timeout: float = 180.0,
    extra_body: Optional[Dict] = None,
) -> Dict[str, Any]:
    """通用流式调用 OpenAI 兼容 chat completions。"""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
        "stream": True,
    }
    if extra_body:
        payload.update(extra_body)
    payload_json = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    url = f"{base_url.rstrip('/')}/chat/completions"
    req = urllib.request.Request(
        url,
        data=payload_json,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )

    content_chunks: list[str] = []
    ttft: Optional[float] = None
    t_connected: Optional[float] = None
    status_code: Optional[int] = None
    usage_info: Optional[Dict] = None
    finish_reason: Optional[str] = None
    error_body: Optional[str] = None

    print(f"   [{label}] POST {url}  model={model}  payload={len(payload_json)/1024:.1f}KB", flush=True)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            status_code = resp.status
            t_connected = now()
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if ttft is None:
                    ttft = now()
                choice = chunk.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                if "content" in delta and delta["content"]:
                    content_chunks.append(delta["content"])
                if "usage" in chunk and chunk["usage"]:
                    usage_info = chunk["usage"]
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")[:500]
        status_code = e.code
    except Exception as e:
        error_body = f"{type(e).__name__}: {e}"

    return {
        "label": label,
        "url": url,
        "status_code": status_code,
        "t_connected": t_connected,
        "ttft": ttft,
        "content_chunks": content_chunks,
        "full_content": "".join(content_chunks),
        "usage": usage_info,
        "finish_reason": finish_reason,
        "error": error_body,
    }


def try_parse_json(text: str) -> Tuple[Optional[Dict], Optional[str]]:
    if not text or not text.strip():
        return None, "empty"
    cleaned = text.strip()
    # 1) 剥 <think>...</think> 块（M3 / deepseek 风格）
    cleaned = re.sub(r"<think>.*?</think>\s*", "", cleaned, flags=re.DOTALL)
    # 2) 剥 ```json``` / ``` 包裹
    if cleaned.startswith("```"):
        first_nl = cleaned.find("\n")
        last_bt = cleaned.rfind("```")
        if first_nl != -1 and last_bt > first_nl:
            cleaned = cleaned[first_nl + 1 : last_bt].strip()
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as e:
        return None, str(e)


def render_summary(name: str, result: Dict[str, Any], t_total_start: float) -> None:
    """打印单家 API 的汇总。"""
    print(f"\n┌─ {name} {'─' * (58 - len(name))}")
    if result["error"]:
        print(f"│ ❌ 失败 (HTTP {result.get('status_code')}): {result['error'][:200]}")
        print(f"└{'─' * 60}")
        return
    usage = result["usage"] or {}
    completion_tokens = usage.get("completion_tokens", 0)
    prompt_tokens = usage.get("prompt_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)
    t_end = result.get("_t_end") or now()
    t_connected = result["t_connected"] or t_total_start
    stream_elapsed = t_end - t_connected
    ttft = result["ttft"]
    tps = completion_tokens / stream_elapsed if stream_elapsed > 0 else 0
    parsed, _ = try_parse_json(result["full_content"])
    print(f"│ HTTP 连接     : {((t_connected - t_total_start) * 1000):>8.1f} ms")
    if ttft:
        print(f"│ 首字节 TTFT   : {((ttft - t_total_start) * 1000):>8.1f} ms")
    print(f"│ 流传输时长    : {(stream_elapsed * 1000):>8.1f} ms")
    print(f"│ tokens in/out : {prompt_tokens:>5} / {completion_tokens:>5}  (total={total_tokens})")
    print(f"│ 生成速度      : {tps:>8.1f} tokens/s")
    print(f"│ finish_reason : {result['finish_reason']}")
    print(f"│ JSON 解析     : {'✅ OK' if parsed else '❌ FAIL'}")
    print(f"│ 输出长度      : {len(result['full_content'])} chars")
    print(f"└{'─' * 60}")


def render_compare_table(m3: Dict, qwen: Dict, t_total_start: float) -> None:
    print("\n" + "=" * 60)
    print("📊 对比表（同图同 prompt 同时压缩后分别调用）")
    print("=" * 60)
    rows = [
        ("指标", "M3 (MiniMax-M3)", "qwen3-vl-flash", "胜出"),
    ]
    # 提取数据
    def safe(r, k, default="—"):
        return r.get(k) if r.get(k) is not None else default

    m3_t_connected = m3.get("t_connected") or t_total_start
    m3_t_end = m3.get("_t_end") or now()
    m3_conn = (m3_t_connected - t_total_start) * 1000
    m3_ttft = ((m3["ttft"] - t_total_start) * 1000) if m3.get("ttft") else None
    m3_stream = (m3_t_end - m3_t_connected) * 1000
    m3_usage = m3.get("usage") or {}
    m3_out = m3_usage.get("completion_tokens", 0)
    m3_tps = m3_out / ((m3_t_end - m3_t_connected)) if (m3_t_end - m3_t_connected) > 0 else 0
    m3_parsed, _ = try_parse_json(m3.get("full_content", ""))

    qw_t_connected = qwen.get("t_connected") or t_total_start
    qw_t_end = qwen.get("_t_end") or now()
    qw_conn = (qw_t_connected - t_total_start) * 1000
    qw_ttft = ((qwen["ttft"] - t_total_start) * 1000) if qwen.get("ttft") else None
    qw_stream = (qw_t_end - qw_t_connected) * 1000
    qw_usage = qwen.get("usage") or {}
    qw_out = qw_usage.get("completion_tokens", 0)
    qw_tps = qw_out / ((qw_t_end - qw_t_connected)) if (qw_t_end - qw_t_connected) > 0 else 0
    qw_parsed, _ = try_parse_json(qwen.get("full_content", ""))

    def winner(smaller_is_better, a, b):
        if a is None or b is None:
            return "—"
        if a == b:
            return "平"
        if smaller_is_better:
            return "M3" if a < b else "qwen"
        return "M3" if a > b else "qwen"

    def fmt(v, suffix=""):
        return f"{v:.1f}{suffix}" if isinstance(v, (int, float)) else str(v)

    lines = [
        ("HTTP 连接", fmt(m3_conn, "ms"), fmt(qw_conn, "ms"), winner(True, m3_conn, qw_conn)),
        ("首字节 TTFT", fmt(m3_ttft, "ms") if m3_ttft else "—", fmt(qw_ttft, "ms") if qw_ttft else "—", winner(True, m3_ttft, qw_ttft)),
        ("流传输时长", fmt(m3_stream, "ms"), fmt(qw_stream, "ms"), winner(True, m3_stream, qw_stream)),
        ("总耗时", fmt(m3_ttft + m3_stream if m3_ttft else m3_stream, "ms"),
                  fmt(qw_ttft + qw_stream if qw_ttft else qw_stream, "ms"),
                  winner(True, m3_ttft + m3_stream if m3_ttft else 0, qw_ttft + qw_stream if qw_ttft else 0)),
        ("output tokens", str(m3_out), str(qw_out), "—"),
        ("生成速度", fmt(m3_tps, " tps"), fmt(qw_tps, " tps"), winner(False, m3_tps, qw_tps)),
        ("finish_reason", str(safe(m3, "finish_reason", "—")), str(safe(qwen, "finish_reason", "—")), "—"),
        ("JSON 解析", "✅" if m3_parsed else "❌", "✅" if qw_parsed else "❌", "—" if (m3_parsed == qw_parsed) else ("M3" if m3_parsed else "qwen")),
        ("输出字符数", str(len(m3.get("full_content", ""))), str(len(qwen.get("full_content", ""))), "—"),
    ]
    for row in lines:
        print(f"  {row[0]:<14} │ {row[1]:<22} │ {row[2]:<22} │ {row[3]}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="M3 vs qwen3-vl-flash 多模态对比")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help=f"图片路径（默认: {DEFAULT_IMAGE}）")
    parser.add_argument("--no-compress", action="store_true", help="跳过图片压缩")
    parser.add_argument("--max-edge", type=int, default=1600, help="压缩后短边最大像素（默认 1600）")
    parser.add_argument("--jpeg-quality", type=int, default=85, help="JPEG 质量（默认 85）")
    parser.add_argument("--env-file", default=DEFAULT_ENV_FILE, help=f"项目 .env 路径（默认: {DEFAULT_ENV_FILE}）")
    # M3
    parser.add_argument("--m3-key", default=os.environ.get("M3_API_KEY", DEFAULT_M3_KEY))
    parser.add_argument("--m3-base-url", default=os.environ.get("M3_BASE_URL", DEFAULT_M3_BASE_URL))
    parser.add_argument("--m3-model", default=os.environ.get("M3_MODEL", DEFAULT_M3_MODEL))
    parser.add_argument("--m3-thinking", action="store_true",
                        help="开启 M3 thinking 模式（默认关闭，关闭时 payload 注入 reasoning={type:disabled}）")
    # DashScope / qwen3-vl
    parser.add_argument("--dashscope-key", default=os.environ.get("DASHSCOPE_API_KEY"))
    parser.add_argument("--dashscope-base-url", default=os.environ.get("DASHSCOPE_BASE_URL", DEFAULT_DASHSCOPE_BASE_URL))
    parser.add_argument("--dashscope-vl-model", default=os.environ.get("DASHSCOPE_VISION_MODEL", DEFAULT_DASHSCOPE_VL_MODEL))
    args = parser.parse_args()

    print("=" * 60)
    print("M3 vs qwen3-vl-flash 多模态对比")
    print("=" * 60)

    # ── 找图片 ──
    image_path = find_image(args.image)
    if not image_path:
        print(f"❌ 找不到图片: {args.image}")
        print(f"   工作目录: {os.getcwd()}")
        return 1
    print(f"image   : {image_path}")

    # ── 解析 .env 拿 DASHSCOPE 配置（如果命令行 / 环境变量没给） ──
    if args.env_file and not args.dashscope_key:
        env = parse_env_file(args.env_file)
        if not args.dashscope_key:
            args.dashscope_key = env.get("DASHSCOPE_API_KEY")
        if args.dashscope_base_url == DEFAULT_DASHSCOPE_BASE_URL:
            args.dashscope_base_url = env.get("DASHSCOPE_BASE_URL", args.dashscope_base_url)
        if args.dashscope_vl_model == DEFAULT_DASHSCOPE_VL_MODEL:
            args.dashscope_vl_model = env.get("DASHSCOPE_VISION_MODEL", args.dashscope_vl_model)
        print(f"env     : {args.env_file}  ({'✅ loaded' if env else '⚠️ not found / empty'})")
    else:
        print(f"env     : 跳过（命令行 / 环境变量已提供 DASHSCOPE_API_KEY）")

    print(f"M3      : base={args.m3_base_url}  model={args.m3_model}  key={args.m3_key[:12]}…{args.m3_key[-6:]}")
    print(f"qwen    : base={args.dashscope_base_url}  model={args.dashscope_vl_model}  key={args.dashscope_key[:12] if args.dashscope_key else '❌ MISSING'}…{args.dashscope_key[-6:] if args.dashscope_key else ''}")
    if not args.dashscope_key:
        print("❌ 缺 DASHSCOPE_API_KEY（--dashscope-key 或环境变量 DASHSCOPE_API_KEY 或 .env）")
        return 1
    if not args.m3_key:
        print("❌ 缺 M3 key（--m3-key 或环境变量 M3_API_KEY）")
        return 1
    print()

    # ── 读取图片 ──
    t_total_start = now()
    t0 = now()
    with open(image_path, "rb") as f:
        raw_bytes = f.read()
    t1 = now()
    print(f"[{t1:.3f}] 原图读取  size={len(raw_bytes)/1024:.1f}KB  耗时={(t1-t0)*1000:.1f}ms")
    print()

    # ── 压缩 ──
    if args.no_compress:
        compressed_bytes = raw_bytes
        print(f"[{now():.3f}] 跳过压缩（--no-compress），使用原图")
    else:
        if not HAS_PIL:
            print("⚠️ Pillow 未安装，跳过压缩（原图直传）。安装: pip install Pillow")
            compressed_bytes = raw_bytes
        else:
            t0 = now()
            compressed_bytes, orig_w, orig_h, new_w, new_h = compress_image(
                raw_bytes, max_edge=args.max_edge, quality=args.jpeg_quality
            )
            t1 = now()
            print(
                f"[{t1:.3f}] Pillow 压缩  {orig_w}x{orig_h} → {new_w}x{new_h}  "
                f"{(len(raw_bytes)/1024):.1f}KB → {(len(compressed_bytes)/1024):.1f}KB  "
                f"(短边≤{args.max_edge}, JPEG q={args.jpeg_quality})  耗时={(t1-t0)*1000:.1f}ms"
            )
    image_b64 = base64.b64encode(compressed_bytes).decode("ascii")
    print(f"[{now():.3f}] base64 编码  {len(image_b64)} chars ({(len(image_b64)/1024):.1f}KB)")
    print()

    # ── 调用 M3 ──
    print("=" * 60)
    print(f"🚀 调用 M3 (MiniMax-M3)  thinking={'ON' if args.m3_thinking else 'OFF'}")
    print("=" * 60)
    m3_extra = {} if args.m3_thinking else {"reasoning": {"type": "disabled"}}
    m3 = call_chat_completions_stream(
        api_key=args.m3_key,
        base_url=args.m3_base_url,
        model=args.m3_model,
        image_b64=image_b64,
        prompt=PROMPT,
        label="M3",
        extra_body=m3_extra,
    )
    m3["_t_end"] = now()
    if not m3["error"]:
        render_summary("M3 (MiniMax-M3)", m3, t_total_start)

    # ── 调用 qwen3-vl-flash ──
    print("\n" + "=" * 60)
    print("🚀 调用 qwen3-vl-flash (DashScope)")
    print("=" * 60)
    qw = call_chat_completions_stream(
        api_key=args.dashscope_key,
        base_url=args.dashscope_base_url,
        model=args.dashscope_vl_model,
        image_b64=image_b64,
        prompt=PROMPT,
        label="qwen3-vl-flash",
    )
    qw["_t_end"] = now()
    if not qw["error"]:
        render_summary("qwen3-vl-flash", qw, t_total_start)

    # ── 对比表 ──
    if not m3["error"] and not qw["error"]:
        render_compare_table(m3, qw, t_total_start)

    # ── 双方原始输出 ──
    print("\n" + "=" * 60)
    print("📝 M3 原始输出")
    print("=" * 60)
    print(m3["full_content"] if m3["full_content"] else "(失败 / 空)")
    m3_parsed, m3_err = try_parse_json(m3["full_content"])
    if m3_parsed:
        print("\n[M3 解析后 JSON]")
        print(json.dumps(m3_parsed, ensure_ascii=False, indent=2))
    elif m3_err and m3_err != "empty":
        print(f"\n[M3 解析失败] {m3_err}")

    print("\n" + "=" * 60)
    print("📝 qwen3-vl-flash 原始输出")
    print("=" * 60)
    print(qw["full_content"] if qw["full_content"] else "(失败 / 空)")
    qw_parsed, qw_err = try_parse_json(qw["full_content"])
    if qw_parsed:
        print("\n[qwen 解析后 JSON]")
        print(json.dumps(qw_parsed, ensure_ascii=False, indent=2))
    elif qw_err and qw_err != "empty":
        print(f"\n[qwen 解析失败] {qw_err}")

    # 退出码：两家都 JSON 成功 = 0，否则 2
    return 0 if (m3_parsed and qw_parsed) else 2


if __name__ == "__main__":
    sys.exit(main())
