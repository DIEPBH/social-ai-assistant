import os
import json
import logging
import requests
from typing import Any, Dict

logger = logging.getLogger(__name__)

class GeminiAnalyzer:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.timeout = 30
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={self.api_key}"

    def analyze_message(self, content: str) -> Dict[str, Any]:
        if not self.api_key:
            logger.error("Missing GEMINI_API_KEY environment variable")
            raise RuntimeError("Missing GEMINI_API_KEY")

        dynamic_topics = self._get_dynamic_topics_text()

        prompt = (
            "Bạn là trợ lý AI cho hệ thống tiếp nhận tin nhắn của cơ quan nhà nước.\n"
            "Hãy phân tích nội dung người dân gửi tới và trả về DUY NHẤT một JSON hợp lệ "
            "với đúng 4 khóa: topic, sentiment, priority, summary.\n"
            f"topic nên ưu tiên một trong các nhóm đang được cấu hình trong hệ thống: {dynamic_topics}.\n"
            "sentiment chỉ được là: tích cực, trung lập, tiêu cực.\n"
            "priority chỉ được là: low, normal, high.\n"
            "summary phải ngắn gọn, rõ nghĩa, bằng tiếng Việt.\n\n"
            f"Nội dung cần phân tích:\n{content}"
        )

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1
            }
        }

        import time
        from social_messages.models import IntegrationLog
        
        start_time = time.time()
        error_msg = ""
        response = None
        data = None
        try:
            logger.info("Calling Gemini API directly")
            response = requests.post(self.url, json=payload, timeout=self.timeout)
            if response.status_code != 200:
                logger.error("Gemini API Error Response: %s", response.text)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            error_msg = str(e)
            logger.exception("Error calling Gemini API: %s", e)
        finally:
            processing_time_ms = (time.time() - start_time) * 1000
            resp_json = {}
            if response:
                try:
                    resp_json = response.json()
                except Exception:
                    resp_json = {"raw_text": response.text}
            
            safe_url = self.url.split("?key=")[0] if "?key=" in self.url else self.url
            IntegrationLog.objects.create(
                system="gemini_api",
                direction="outbound",
                endpoint=safe_url,
                method="POST",
                status_code=response.status_code if response else None,
                request_payload=payload,
                response_payload=resp_json,
                error_message=error_msg,
                processing_time_ms=processing_time_ms
            )

        if error_msg:
            raise RuntimeError(f"Gemini API Error: {error_msg}")

        if data and "candidates" in data and len(data["candidates"]) > 0:
            content_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return self._parse_json_response(content_text)
        else:
            logger.error("Gemini API returned unexpected format: %s", data)
            raise RuntimeError("No candidates found in Gemini response")

    def _get_dynamic_topics_text(self) -> str:
        try:
            from ..models import TopicDefinition
            active_topics = TopicDefinition.objects.filter(is_active=True).values_list("name", flat=True)
            if active_topics:
                return ", ".join(active_topics)
            return "chưa cấu hình"
        except Exception:
            return "tin báo tội phạm, trật tự công cộng, vệ sinh môi trường, thủ tục hành chính, khiếu nại tố cáo, khác"

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        try:
            # Strip markdown if present
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            data = json.loads(text)
            return {
                "topic": data.get("topic", "khác"),
                "sentiment": data.get("sentiment", "trung lập"),
                "priority": data.get("priority", "normal"),
                "summary": data.get("summary", "Nội dung người dân gửi: " + text[:50]),
            }
        except Exception as e:
            logger.error("Failed to parse JSON from Gemini: %s. Raw text: %s", e, text)
            raise RuntimeError(f"Gemini returned invalid JSON content: {e}")
