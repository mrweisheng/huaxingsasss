"""
LLM客户端 - 阿里云百炼 DashScope（qwen3-vl-flash 视觉模型 + deepseek-v4-flash Agent 推理）
"""
import asyncio
import base64
import json
import logging
import re
from typing import Dict, Any, Optional, AsyncGenerator, List
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class SiliconFlowClient:
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
                            "text": self._build_contract_extraction_prompt()
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
            raise Exception(f"SiliconFlow API error: {response.text}")

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
    
    def _build_contract_extraction_prompt(self) -> str:
        """构建合同解析Prompt"""
        return """
你是一个专业的合同信息提取助手，专门处理两地车牌指标过户服务相关的合同。请仔细分析这张合同图片，提取以下关键信息并以严格的JSON格式返回：

{
  "contract_number": "合同编号（字符串）",
  "title": "合同标题（字符串）",
  "signed_date": "签订日期（YYYY-MM-DD格式）",
  "business_type": "业务类型：车辆业务 或 中港牌业务",
  "business_description": "一句话业务描述，如：购买丰田阿尔法30系、办理深圳湾口岸中港车牌",
  "party_a": {
    "name": "甲方名称（字符串）",
    "contact": "联系方式（字符串）",
    "address": "地址（字符串，如无则为null）"
  },
  "party_b": {
    "name": "乙方姓名（字符串）",
    "id_info": "证件信息（字符串，原文照抄：可能含证件名称+号码，也可能只有号码。不要根据号码特征推断证件类型——F/字母开头不一定是通行证，18位数字不一定是身份证）",
    "phone": "联系电话（字符串）",
    "address": "地址（字符串，如无则为null）"
  },
  "vehicle_info": {
    "plate_number": "车牌号（字符串，如无则为null）",
    "vehicle_model": "车型，如丰田阿尔法30系（字符串，如无则为null）",
    "registration_number": "登记编号（字符串，如无则为null）"
  },
  "port": "通行口岸，如深圳湾口岸、皇岗口岸（仅中港牌业务，如无则为null）",
  "service_items": [
    {
      "name": "服务项目名称",
      "description": "描述",
      "amount": 项目金额（数字）
    }
  ],
  "payment_terms": [
    {
      "name": "款项名称（如定金/尾款/第一期）",
      "amount": 金额（数字类型）,
      "due_date": "应付款日期（YYYY-MM-DD格式，如无则为null）",
      "condition": "支付条件",
      "is_paid": 是否已支付（布尔值）。根据合同原文判断：合同明确标注已付/已缴纳/付清/已收则为true，否则为false
    }
  ],
  "total_amount": 合同总金额（数字类型）,
  "currency": "币种（CNY/HKD）",
  "validity_period": {
    "start_date": "生效日期（YYYY-MM-DD格式，如无则为null）",
    "end_date": "到期日期（YYYY-MM-DD格式，如无则为null）"
  },
  "special_terms": ["特殊条款列表"],
  "confidence": 置信度（0-1之间的数字）,
  "full_text": "合同的完整文本内容。将图片/PDF中所有可见的文字逐字转录，包括全部条款、双方信息、金额、日期、签名栏等。保持原文段落结构，不要总结或省略。繁体中文原样保留。"
}

严格要求：
1. 只返回纯JSON，不要包含markdown格式或其他文字说明
2. 如果某个字段无法识别，设为null，数组字段设为空数组[]
3. 金额统一转换为数字类型
4. 日期统一为YYYY-MM-DD格式
5. business_type判断规则：涉及购车/卖车为"车辆业务"，涉及车牌办理/过户/新办为"中港牌业务"
6. business_description要具体，提取车型、口岸等关键信息
7. full_text 必须完整转录合同中的所有文字，不得省略条款、不得改写内容。繁体中文原样保留，不得转为简体。
8. 确保JSON格式合法
        """.strip()
    
    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取JSON部分"""
        match = re.search(r'```json\s*(\{.*\})\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

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


class DashScopeAgentClient:
    """Agent 推理客户端（硅基流动 SiliconFlow DeepSeek-V4-Flash）

    通过 OpenAI 兼容 API 调用，支持流式输出、函数调用和指数退避重试。
    使用 SILICONFLOW_* 配置，与视觉模型（DASHSCOPE_*）独立。
    """

    def __init__(self):
        self.api_key = settings.SILICONFLOW_API_KEY
        self.base_url = settings.SILICONFLOW_BASE_URL
        self.model = settings.SILICONFLOW_AGENT_MODEL
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
        流式调用 SiliconFlow Agent 模型，支持函数调用和指数退避重试。
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
                        "SiliconFlow Agent 请求: model=%s, base_url=%s, attempt=%d/%d",
                        self.model, self.base_url, attempt + 1, self.max_retries,
                    )
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    ) as response:
                        logger.info(
                            "SiliconFlow Agent 响应状态: %d, content_type=%s",
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
                                "SiliconFlow Agent 限流 429，%.1fs 后重试 (attempt %d/%d)",
                                retry_after, attempt + 1, self.max_retries,
                            )
                            await response.aread()
                            await asyncio.sleep(retry_after)
                            continue

                        if response.status_code >= 500:
                            delay = self.retry_base_delay * (2 ** attempt)
                            logger.warning(
                                "SiliconFlow Agent 服务端错误 %d，%.1fs 后重试 (attempt %d/%d)",
                                response.status_code, delay, attempt + 1, self.max_retries,
                            )
                            await response.aread()
                            await asyncio.sleep(delay)
                            continue

                        if response.status_code >= 400:
                            error_body = await response.aread()
                            raise Exception(
                                f"SiliconFlow Agent API error {response.status_code}: {error_body.decode()}"
                            )

                        # 成功：处理 SSE 流
                        current_tool_calls: dict = {}
                        sse_line_count = 0

                        async for line in response.aiter_lines():
                            sse_line_count += 1
                            if sse_line_count <= 3:
                                logger.debug("SiliconFlow Agent SSE line #%d: %s", sse_line_count, line[:200] if len(line) > 200 else line)
                            if not line.startswith("data: "):
                                continue
                            data = line[6:]
                            if data == "[DONE]":
                                logger.info("SiliconFlow Agent SSE 流结束, 共 %d 行", sse_line_count)
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
                                        "SiliconFlow Agent 流式返回 length 截断且含 tool_calls，"
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
                            "SiliconFlow Agent 流传输中途断开（已 yield %d 个事件），放弃重试: %s",
                            yielded_count, type(e).__name__,
                        )
                        raise
                    last_error = e
                    delay = self.retry_base_delay * (2 ** attempt)
                    logger.warning(
                        "SiliconFlow Agent 网络错误: %s，%.1fs 后重试 (attempt %d/%d)",
                        type(e).__name__, delay, attempt + 1, self.max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue

        raise Exception(
            f"SiliconFlow Agent API 在 {self.max_retries} 次重试后仍失败: {last_error}"
        )

    async def analyze_image_with_vl(
        self,
        image_path: str,
        prompt: str,
    ) -> Dict[str, Any]:
        """使用百炼 VL 模型分析图片（复用 SiliconFlowClient）"""
        sf_client = SiliconFlowClient()

        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()

        payload = {
            "model": sf_client.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        headers = {
            "Authorization": f"Bearer {sf_client.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{sf_client.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )

        if response.status_code != 200:
            raise Exception(f"VL API error: {response.text}")

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        try:
            structured_data = json.loads(content)
        except json.JSONDecodeError:
            structured_data = sf_client._extract_json_from_text(content)

        return {
            "data": structured_data,
            "tokens_used": result.get("usage", {}).get("total_tokens", 0),
        }
