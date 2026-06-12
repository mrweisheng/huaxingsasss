"""
LLM客户端 - 阿里云百炼 DashScope（qwen3-vl-flash 视觉模型）+ DeepSeek 官方（Agent 推理 + 文本结构化）

类名说明：
  - VisionModelClient: 百炼 qwen3-vl-flash 视觉模型（合同/凭证图片分析）
  - AgentModelClient:  DeepSeek 官方（Agent 推理 + 工具调用 + PDF/Word 文本结构化）
"""
import asyncio
import base64
import json
import logging
import re
from typing import Dict, Any, Optional, AsyncGenerator, List
import httpx
from app.config import settings
# Prompt 统一：parse_contract_image 改用 prompts_v2 的权威常量，
# 消除内联旧版与 prompts_v2.py 新版 business_type 枚举不一致的问题。
from app.ai.prompts_v2 import CONTRACT_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)


class VisionModelClient:
    """VL 视觉模型客户端（阿里云百炼 qwen3-vl-flash，兼容模式 API）"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        self.base_url = settings.DASHSCOPE_BASE_URL
        self.vision_model = settings.DASHSCOPE_VISION_MODEL

    async def parse_contract_image(self, image_path: str) -> Dict[str, Any]:
        """
        解析合同图片，提取结构化数据（异步）

        Args:
            image_path: 合同图片本地路径

        Returns:
            {
                "data": {...},
                "confidence": 0.92,
                "raw_response": "...",
                "tokens_used": 1500
            }
        """
        # 读取图片并转base64
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()

        # 构造请求
        payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            # 修复（P2-5）：统一使用 prompts_v2 中的权威 Prompt
                            "text": CONTRACT_ANALYSIS_PROMPT
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4096
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 异步调用API
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )

        if response.status_code != 200:
            raise Exception(f"DashScope API error: {response.text}")

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # 尝试解析JSON
        try:
            structured_data = json.loads(content)
        except json.JSONDecodeError:
            structured_data = self._extract_json_from_text(content)

        return {
            "data": structured_data,
            "confidence": self._calculate_confidence(structured_data),
            "raw_response": content,
            "tokens_used": result.get("usage", {}).get("total_tokens", 0)
        }

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取JSON部分"""
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # 通用 fallback：必须用贪婪匹配，非贪婪会在嵌套 JSON 的第一个 } 处截断
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise ValueError("无法从响应中提取JSON")
    
    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """计算解析置信度"""
        key_fields = ["contract_number", "party_a", "party_b", "total_amount"]
        present_fields = sum(1 for field in key_fields if data.get(field))
        
        base_confidence = present_fields / len(key_fields)
        
        if data.get("payment_terms"):
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)


class AgentModelClient:
    """Agent 推理客户端（DeepSeek 官方 API）

    通过 OpenAI 兼容 API 调用，支持流式输出、函数调用和指数退避重试。
    使用 DEEPSEEK_* 配置，与视觉模型（DASHSCOPE_*）独立。
    """

    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_BASE_URL
        self.model = settings.DEEPSEEK_AGENT_MODEL
        self.max_retries = getattr(settings, 'AGENT_MAX_RETRIES', 3)
        self.retry_base_delay = getattr(settings, 'AGENT_RETRY_BASE_DELAY', 1.0)

    async def chat_completion_stream(
        self,
        messages: List[dict],
        tools: Optional[List[dict]] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[dict, None]:
        """
        流式调用 DeepSeek Agent 模型，支持函数调用和指数退避重试。
        逐个 yield 解析后的 SSE 事件。

        重试条件：429（限流）、5xx（服务端错误）、TimeoutException、ConnectError
        不重试：4xx（客户端错误，除 429 外）、流已开始传输后断开

        Yields:
            {"type": "text", "content": "..."} — 文本增量
            {"type": "tool_call", "id": "...", "name": "...", "arguments": "..."} — 工具调用
            {"type": "done", "finish_reason": "..."} — 完成
        """
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "enable_thinking": False,  # 关闭推理模式，函数调用必须关闭
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        timeout_config = httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=15.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            for attempt in range(self.max_retries):
                yielded_count = 0
                try:
                    logger.info(
                        "DeepSeek Agent 请求: model=%s, base_url=%s, attempt=%d/%d",
                        self.model, self.base_url, attempt + 1, self.max_retries,
                    )
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    ) as response:
                        logger.info(
                            "DeepSeek Agent 响应状态: %d, content_type=%s",
                            response.status_code,
                            response.headers.get("content-type", "unknown"),
                        )
                        if response.status_code == 429:
                            try:
                                retry_after = float(response.headers.get("retry-after", ""))
                            except (ValueError, TypeError):
                                retry_after = self.retry_base_delay * (2 ** attempt)
                            retry_after = max(retry_after, self.retry_base_delay)
                            logger.warning(
                                "DeepSeek Agent 限流 429，%.1fs 后重试 (attempt %d/%d)",
                                retry_after, attempt + 1, self.max_retries,
                            )
                            await response.aread()
                            await asyncio.sleep(retry_after)
                            continue

                        if response.status_code >= 500:
                            delay = self.retry_base_delay * (2 ** attempt)
                            logger.warning(
                                "DeepSeek Agent 服务端错误 %d，%.1fs 后重试 (attempt %d/%d)",
                                response.status_code, delay, attempt + 1, self.max_retries,
                            )
                            await response.aread()
                            await asyncio.sleep(delay)
                            continue

                        if response.status_code >= 400:
                            error_body = await response.aread()
                            raise Exception(
                                f"DeepSeek Agent API error {response.status_code}: {error_body.decode()}"
                            )

                        # 成功：处理 SSE 流
                        current_tool_calls: dict = {}
                        sse_line_count = 0

                        async for line in response.aiter_lines():
                            sse_line_count += 1
                            if sse_line_count <= 3:
                                logger.debug("DeepSeek Agent SSE line #%d: %s", sse_line_count, line[:200] if len(line) > 200 else line)
                            if not line.startswith("data: "):
                                continue
                            data = line[6:]
                            if data == "[DONE]":
                                logger.info("DeepSeek Agent SSE 流结束, 共 %d 行", sse_line_count)
                                for tc in current_tool_calls.values():
                                    yield {
                                        "type": "tool_call",
                                        "id": tc["id"],
                                        "name": tc["name"],
                                        "arguments": tc.get("arguments", ""),
                                    }
                                yield {"type": "done", "finish_reason": "stop"}
                                return

                            try:
                                chunk = json.loads(data)
                            except json.JSONDecodeError:
                                continue

                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            finish_reason = chunk.get("choices", [{}])[0].get("finish_reason")

                            content = delta.get("content")
                            if content:
                                yield {"type": "text", "content": content}
                                yielded_count += 1

                            tool_calls = delta.get("tool_calls")
                            if tool_calls:
                                for tc in tool_calls:
                                    idx = tc.get("index", 0)
                                    if idx not in current_tool_calls:
                                        current_tool_calls[idx] = {
                                            "id": tc.get("id", ""),
                                            "name": tc.get("function", {}).get("name", ""),
                                            "arguments": "",
                                        }
                                    if tc.get("id"):
                                        current_tool_calls[idx]["id"] = tc["id"]
                                    fn = tc.get("function", {})
                                    if fn.get("name"):
                                        current_tool_calls[idx]["name"] = fn["name"]
                                    if fn.get("arguments"):
                                        current_tool_calls[idx]["arguments"] += fn["arguments"]

                            usage = chunk.get("usage")
                            if usage:
                                yield {
                                    "type": "usage",
                                    "prompt_tokens": usage.get("prompt_tokens", 0),
                                    "completion_tokens": usage.get("completion_tokens", 0),
                                    "total_tokens": usage.get("total_tokens", 0),
                                }

                            if finish_reason == "tool_calls":
                                for tc in current_tool_calls.values():
                                    yield {
                                        "type": "tool_call",
                                        "id": tc["id"],
                                        "name": tc["name"],
                                        "arguments": tc.get("arguments", ""),
                                    }
                                current_tool_calls = {}
                                yield {"type": "done", "finish_reason": "tool_calls"}
                                return

                            if finish_reason == "length":
                                if current_tool_calls:
                                    logger.warning(
                                        "DeepSeek Agent 流式返回 length 截断且含 tool_calls，"
                                        "已强制 flush %d 个工具调用",
                                        len(current_tool_calls),
                                    )
                                    for tc in current_tool_calls.values():
                                        yield {
                                            "type": "tool_call",
                                            "id": tc["id"],
                                            "name": tc["name"],
                                            "arguments": tc.get("arguments", ""),
                                        }
                                    current_tool_calls = {}
                                    yield {"type": "done", "finish_reason": "tool_calls"}
                                    return
                                yield {"type": "done", "finish_reason": "length"}
                                return

                            if finish_reason == "stop":
                                if current_tool_calls:
                                    for tc in current_tool_calls.values():
                                        yield {
                                            "type": "tool_call",
                                            "id": tc["id"],
                                            "name": tc["name"],
                                            "arguments": tc.get("arguments", ""),
                                        }
                                yield {"type": "done", "finish_reason": "stop"}
                                return
                        return

                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    if yielded_count > 0:
                        logger.error(
                            "DeepSeek Agent 流传输中途断开（已 yield %d 个事件），放弃重试: %s",
                            yielded_count, type(e).__name__,
                        )
                        raise
                    last_error = e
                    delay = self.retry_base_delay * (2 ** attempt)
                    logger.warning(
                        "DeepSeek Agent 网络错误: %s，%.1fs 后重试 (attempt %d/%d)",
                        type(e).__name__, delay, attempt + 1, self.max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue

        raise Exception(
            f"DeepSeek Agent API 在 {self.max_retries} 次重试后仍失败: {last_error}"
        )

