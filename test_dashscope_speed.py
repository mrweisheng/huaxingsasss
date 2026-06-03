"""
测试百炼 DashScope DeepSeek-V4-Flash 响应速度
提取 PDF 文本 -> 调用 DashScope Generation API -> 输出耗时统计
"""
import os
import sys
import time
import fitz  # PyMuPDF
from dashscope import Generation

# 修复 Windows 中文终端编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ========================================
# 配置
# ========================================
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-ef4b84cfa9654213a14c0fd83213a16e")
PDF_PATH = r"D:\CODE PROJECT\huaxingsasss\胡少棟 深圳灣現牌合同.pdf"
MODEL = "deepseek-v4-flash"

# ========================================
# 1. 提取 PDF 文本
# ========================================
print("=" * 60)
print("[Step 1] 提取 PDF 文本内容")
print("=" * 60)

t0 = time.time()
doc = fitz.open(PDF_PATH)
all_pages = []
for i, page in enumerate(doc):
    text = page.get_text()
    all_pages.append(text)
doc.close()

full_text = "\n".join(all_pages)
text_extract_time = time.time() - t0

print(f"  PDF 页数: {len(all_pages)}")
print(f"  文本字符数: {len(full_text)}")
print(f"  提取耗时: {text_extract_time:.2f}s")

# 截取前 8000 字符（与项目中 tools.py 保持一致）
truncated = full_text[:8000]
print(f"  截取发送: {len(truncated)} 字符")

# ========================================
# 2. 构建 Prompt
# ========================================
prompt_text = f"""你是一个专业的合同分析助手。请仔细阅读以下合同文本，提取关键信息并以 JSON 格式返回。

要求返回以下字段：
- contract_number: 合同编号
- total_amount: 合同总金额（数字）
- currency: 币种（CNY/HKD/USD）
- party_a_name: 甲方名称
- party_b_name: 乙方名称
- signed_date: 签订日期
- payment_terms: 付款条款列表
- special_terms: 特殊条款

以下是合同文本：

{truncated}"""

print()
print("=" * 60)
print("[Step 2] 调用 DashScope DeepSeek-V4-Flash")
print("=" * 60)
print(f"  模型: {MODEL}")
print(f"  提示词长度: {len(prompt_text)} 字符")
print(f"  enable_thinking: False")
print()

# ========================================
# 3. 调用 API 并计时
# ========================================
t1 = time.time()

response = Generation.call(
    api_key=DASHSCOPE_API_KEY,
    model=MODEL,
    messages=[{"role": "user", "content": prompt_text}],
    result_format="message",
    enable_thinking=False,
)

api_time = time.time() - t1

# ========================================
# 4. 输出结果
# ========================================
print("=" * 60)
print("[Step 3] 结果分析")
print("=" * 60)

if response.status_code == 200:
    output = response.output
    choice = output.choices[0]
    msg = choice.message

    # 思考过程（仅 enable_thinking=True 时才有）
    try:
        reasoning = msg.reasoning_content
    except Exception:
        reasoning = None
    if reasoning:
        print(f"\n[思考过程] ({len(reasoning)} 字符):")
        print("-" * 40)
        # 只打印前500字符和后200字符
        if len(reasoning) > 800:
            print(reasoning[:500])
            print(f"\n  ... (省略 {len(reasoning) - 700} 字符) ...\n")
            print(reasoning[-200:])
        else:
            print(reasoning)
        print("-" * 40)

    # 回复内容
    try:
        content = msg.content
    except Exception:
        content = ""
    print(f"\n[模型回复] ({len(content)} 字符):")
    print("-" * 40)
    print(content[:1000])
    if len(content) > 1000:
        print(f"\n  ... (省略 {len(content) - 1000} 字符) ...")
    print("-" * 40)

    # Token 统计
    try:
        usage = output.usage
        if usage:
            print(f"\n[Token 统计]:")
            input_tokens = getattr(usage, 'input_tokens', 0)
            output_tokens = getattr(usage, 'output_tokens', 0)
            total_tokens = getattr(usage, 'total_tokens', 0)
            print(f"  输入 tokens: {input_tokens}")
            print(f"  输出 tokens: {output_tokens}")
            print(f"  总 tokens: {total_tokens}")
    except Exception:
        pass

    finish_reason = choice.finish_reason
    print(f"\n[OK] 完成原因: {finish_reason}")

else:
    print(f"\n[FAIL] API 调用失败!")
    print(f"  状态码: {response.status_code}")
    print(f"  错误码: {response.code}")
    print(f"  错误信息: {response.message}")

# ========================================
# 5. 耗时汇总
# ========================================
print()
print("=" * 60)
print("[耗时汇总]")
print("=" * 60)
total = text_extract_time + api_time
print(f"  PDF 文本提取: {text_extract_time:.2f}s")
print(f"  API 调用:     {api_time:.2f}s")
print(f"  总计:         {total:.2f}s")

if api_time > 0:
    char_speed = len(content) / api_time if response.status_code == 200 else 0
    print(f"  生成速度:     {char_speed:.0f} 字符/秒")
