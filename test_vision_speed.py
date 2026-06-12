"""测试 qwen3-vl-plus 视觉模型速度（对比 flash）"""
import base64
import time
import os
from openai import OpenAI

API_KEY = "sk-ef4b84cfa9654213a14c0fd83213a16e"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
IMAGE_PATH = os.path.join(os.path.dirname(__file__), "车.jpg")

PROMPT = "请识别这张收据图片中的金额数字（小写），只输出数字，不要任何其他内容。"

MODELS = ["qwen3-vl-flash", "qwen3-vl-plus"]


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def test_model(model: str, b64: str) -> dict:
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                },
                {"type": "text", "text": PROMPT},
            ],
        }
    ]

    # 非流式，测首 token + 总耗时
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=64,
    )
    elapsed = time.perf_counter() - t0

    content = resp.choices[0].message.content or ""
    usage = resp.usage
    return {
        "model": model,
        "answer": content.strip(),
        "elapsed_s": round(elapsed, 2),
        "prompt_tokens": usage.prompt_tokens if usage else "?",
        "completion_tokens": usage.completion_tokens if usage else "?",
        "total_tokens": usage.total_tokens if usage else "?",
    }


def main():
    if not os.path.exists(IMAGE_PATH):
        print(f"图片不存在: {IMAGE_PATH}")
        return

    b64 = encode_image(IMAGE_PATH)
    print(f"图片大小: {os.path.getsize(IMAGE_PATH) / 1024:.0f} KB, base64 长度: {len(b64)}")
    print(f"提示词: {PROMPT}\n")

    results = []
    for model in MODELS:
        print(f"测试 {model} ...")
        r = test_model(model, b64)
        results.append(r)
        print(f"  结果: {r['answer']}  耗时: {r['elapsed_s']}s  tokens: {r['total_tokens']}")

    print("\n" + "=" * 50)
    print("对比结果:")
    print(f"{'模型':<20} {'识别结果':<12} {'耗时(s)':<10} {'tokens':<8}")
    print("-" * 50)
    for r in results:
        print(f"{r['model']:<20} {r['answer']:<12} {r['elapsed_s']:<10} {r['total_tokens']:<8}")


if __name__ == "__main__":
    main()
