import json
import os
from typing import Any, Dict

import requests


class OpenClawAnalyzer:
    """
    Adapter gọi trực tiếp OpenClaw Gateway qua OpenAI-compatible HTTP API.
    Nếu OpenClaw lỗi hoặc trả dữ liệu không đúng định dạng, sẽ fallback.
    """

    def __init__(self) -> None:
        self.base_url = os.getenv("OPENCLOW_BASE_URL", "http://openclaw:18789").rstrip("/")
        self.timeout = int(os.getenv("OPENCLOW_TIMEOUT", "30"))
        self.gateway_token = os.getenv("OPENCLOW_GATEWAY_TOKEN", "")

    def analyze_message(self, content: str) -> Dict[str, Any]:
        try:
            return self._call_openclaw_chat_completions(content)
        except Exception as exc:
            fallback = self._fallback_analysis(content)
            fallback["engine"] = "openclaw_service_fallback"
            fallback["raw_result"]["fallback_reason"] = str(exc)
            return fallback

    def _call_openclaw_chat_completions(self, content: str) -> Dict[str, Any]:
        if not self.gateway_token:
            raise RuntimeError("Missing OPENCLOW_GATEWAY_TOKEN")

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.gateway_token}",
        }

        payload = {
            "model": "openclaw/default",
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý phân tích tin nhắn khách hàng. "
                        "Hãy trả về DUY NHẤT một JSON hợp lệ với các khóa: "
                        "topic, sentiment, priority, summary. "
                        "sentiment chỉ được là: tích cực, trung lập, tiêu cực. "
                        "priority chỉ được là: low, normal, high."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Nội dung khách hàng: {content}",
                },
            ],
        }

        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        message_content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        parsed = json.loads(message_content)

        return {
            "topic": parsed.get("topic", "khác"),
            "sentiment": parsed.get("sentiment", "trung lập"),
            "priority": parsed.get("priority", "normal"),
            "summary": parsed.get("summary", f"Khách gửi tin nhắn: {content or ''}"),
            "engine": "openclaw_service",
            "raw_result": {
                "openclaw_response": data,
                "parsed_content": parsed,
            },
        }

    def _fallback_analysis(self, content: str) -> Dict[str, Any]:
        normalized = (content or "").strip().lower()

        topic = "khác"
        sentiment = "trung lập"
        priority = "normal"
        summary = f"Khách gửi tin nhắn: {content or ''}"

        if any(keyword in normalized for keyword in ["giá", "bao nhiêu", "báo giá"]):
            topic = "hỏi giá"
        elif any(keyword in normalized for keyword in ["lỗi", "không được", "không đăng ký", "không vào được"]):
            topic = "hỗ trợ kỹ thuật"
            sentiment = "tiêu cực"
            priority = "high"
        elif any(keyword in normalized for keyword in ["khiếu nại", "phàn nàn", "bực", "tệ"]):
            topic = "khiếu nại"
            sentiment = "tiêu cực"
            priority = "high"
        elif any(keyword in normalized for keyword in ["cảm ơn", "ok", "được rồi"]):
            topic = "phản hồi tích cực"
            sentiment = "tích cực"

        return {
            "topic": topic,
            "sentiment": sentiment,
            "priority": priority,
            "summary": summary,
            "engine": "stub",
            "raw_result": {
                "normalized_content": normalized,
                "matched_by": "keyword_rules_v1",
            },
        }