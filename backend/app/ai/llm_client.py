"""
LLM客户端 - SiliconFlow Qwen-VL集成
"""
import base64
import json
import re
from typing import Dict, Any, Optional
import httpx
from app.config import settings


class SiliconFlowClient:
    """SiliconFlow Qwen-VL API客户端（异步）"""

    def __init__(self):
        self.api_key = settings.SILICONFLOW_API_KEY
        self.base_url = settings.SILICONFLOW_BASE_URL
        self.vision_model = settings.SILICONFLOW_VISION_MODEL
        self.text_model = settings.SILICONFLOW_TEXT_MODEL

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
        async with httpx.AsyncClient(timeout=60.0) as client:
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
你是一个专业的合同信息提取助手。请仔细分析这张合同图片，提取以下关键信息并以严格的JSON格式返回：

{
  "contract_number": "合同编号（字符串）",
  "title": "合同标题（字符串）",
  "signed_date": "签订日期（YYYY-MM-DD格式）",
  "party_a": {
    "name": "甲方名称（字符串）",
    "contact": "联系方式（字符串）",
    "address": "地址（字符串，如无则为null）"
  },
  "party_b": {
    "name": "乙方姓名（字符串）",
    "id_type": "证件类型（字符串）",
    "id_number": "证件号码（字符串）",
    "address": "地址（字符串，如无则为null）"
  },
  "service_content": {
    "description": "服务内容描述（字符串）",
    "license_plate": "车牌号（字符串，如无则为null）",
    "port": "通行口岸（字符串，如无则为null）"
  },
  "payment_terms": [
    {
      "type": "款项类型（deposit/final/installment）",
      "name": "款项名称（字符串）",
      "amount": 金额（数字类型）,
      "condition": "支付条件（字符串）",
      "due_date": "应付款日期（YYYY-MM-DD格式，如无则为null）"
    }
  ],
  "total_amount": 合同总金额（数字类型）,
  "currency": "币种（CNY/HKD/USD）"
}

严格要求：
1. 只返回纯JSON，不要包含markdown格式或其他文字说明
2. 如果某个字段无法识别，设为null
3. 金额统一转换为数字类型
4. 日期统一为YYYY-MM-DD格式
5. 确保JSON格式合法
        """.strip()
    
    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取JSON部分"""
        import re
        
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
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

    async def answer_question(self, question: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于上下文数据回答问题（异步）

        Args:
            question: 用户问题
            context_data: 从数据库查询的真实数据

        Returns:
            {"answer": "...", "tokens_used": 180, "confidence": 0.9}
        """
        # 基本输入清理：截断长度并移除可能的 prompt 注入模式
        question = question[:2000]
        question = re.sub(r'(忽略|忽略以上|disregard|ignore).*(指令|instructions?|rules?)', '', question, flags=re.IGNORECASE)

        prompt = f"""你是一个专业的业务助手。请基于以下真实数据回答用户问题，不要编造任何信息。

【可用数据】
{json.dumps(context_data, ensure_ascii=False, indent=2)}

【用户问题】
{question}

【回答要求】
1. 只基于上述数据回答，如果数据中没有相关信息，明确告知用户
2. 使用自然、友好的语气
3. 保留关键数字和单位（如金额保留"元"）
4. 如果涉及多个项目，使用列表清晰展示
5. 回答长度控制在200字以内
6. 如果数据不足以回答问题，说明缺少什么信息""".strip()

        payload = {
            "model": self.text_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 512
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )

        if response.status_code != 200:
            raise Exception(f"SiliconFlow API error: {response.text}")

        result = response.json()
        answer = result["choices"][0]["message"]["content"]

        return {
            "answer": answer,
            "tokens_used": result.get("usage", {}).get("total_tokens", 0),
            "confidence": 0.9
        }
