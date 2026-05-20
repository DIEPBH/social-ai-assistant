import json
import os
import re
from typing import Any, Dict

import requests


class OpenClawAnalyzer:
    """
    Adapter gọi OpenClaw Gateway qua OpenAI-compatible HTTP API.

    Đầu ra chuẩn hóa cho dự án:
    - topic
    - sentiment
    - priority
    - summary

    Hỗ trợ:
    - text message bình thường
    - dict intake đã chuẩn hóa từ IntakeSubmission
    """

    ALLOWED_SENTIMENTS = {"tích cực", "trung lập", "tiêu cực"}
    ALLOWED_PRIORITIES = {"low", "normal", "high"}

    def _get_dynamic_topics_text(self) -> str:
        try:
            from social_messages.models import IntakeCategory
            topics = []
            for category in IntakeCategory.objects.filter(is_active=True).order_by("menu_order", "id"):
                topics.append(category.default_topic or category.name)
            return ", ".join(dict.fromkeys([topic for topic in topics if topic])) or "khác"
        except Exception:
            return "khiếu nại, tin báo tội phạm, thủ tục hành chính, hỗ trợ kỹ thuật, khác"

    def __init__(self) -> None:
        self.base_url = os.getenv("OPENCLOW_BASE_URL", "http://openclaw:18789").rstrip("/")
        self.timeout = int(os.getenv("OPENCLOW_TIMEOUT", "30"))
        self.gateway_token = os.getenv("OPENCLOW_GATEWAY_TOKEN", "")

    def analyze_message(self, content: Any) -> Dict[str, Any]:
        normalized_text = self._normalize_input(content)

        try:
            return self._call_openclaw_chat_completions(normalized_text)
        except Exception as exc:
            fallback = self._fallback_analysis(normalized_text)
            fallback["engine"] = "openclaw_service_fallback"
            fallback["raw_result"]["fallback_reason"] = str(exc)
            return fallback

    def _normalize_input(self, content: Any) -> str:
        if isinstance(content, (dict, list)):
            return json.dumps(content, ensure_ascii=False)
        return str(content or "").strip()

    def _call_openclaw_chat_completions(self, content: str) -> Dict[str, Any]:
        if not self.gateway_token:
            raise RuntimeError("Missing OPENCLOW_GATEWAY_TOKEN")

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.gateway_token}",
        }

        dynamic_topics = self._get_dynamic_topics_text()

        payload = {
            "model": "openclaw/default",
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý AI cho hệ thống tiếp nhận tin nhắn của cơ quan nhà nước. "
                        "Hãy phân tích nội dung người dân gửi tới và trả về DUY NHẤT một JSON hợp lệ "
                        "với đúng 4 khóa: topic, sentiment, priority, summary. "
                        f"topic nên ưu tiên một trong các nhóm đang được cấu hình trong hệ thống: {dynamic_topics}. "
                        "sentiment chỉ được là: tích cực, trung lập, tiêu cực. "
                        "priority chỉ được là: low, normal, high. "
                        "summary phải ngắn gọn, rõ nghĩa, bằng tiếng Việt."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Nội dung cần phân tích:\n{content}",
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

        parsed = self._parse_json_response(message_content)

        topic = self._normalize_topic(parsed.get("topic", "khác"))
        sentiment = self._normalize_sentiment(parsed.get("sentiment", "trung lập"))
        priority = self._normalize_priority(parsed.get("priority", "normal"))
        summary = str(parsed.get("summary") or f"Nội dung người dân gửi: {content[:500]}").strip()

        return {
            "topic": topic,
            "sentiment": sentiment,
            "priority": priority,
            "summary": summary,
            "engine": "openclaw_service",
            "raw_result": {
                "openclaw_response": data,
                "raw_message_content": message_content,
                "parsed_content": parsed,
            },
        }

    def _parse_json_response(self, message_content: str) -> Dict[str, Any]:
        message_content = (message_content or "").strip()

        try:
            parsed = json.loads(message_content)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", message_content, re.DOTALL)
        if fenced_match:
            try:
                parsed = json.loads(fenced_match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        object_match = re.search(r"(\{.*\})", message_content, re.DOTALL)
        if object_match:
            try:
                parsed = json.loads(object_match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        raise ValueError(f"OpenClaw returned invalid JSON content: {message_content}")

    def _normalize_topic(self, topic: Any) -> str:
        raw = str(topic or "").strip().lower()

        try:
            from social_messages.models import IntakeCategory
            for category in IntakeCategory.objects.filter(is_active=True):
                candidates = [category.name, category.code, category.default_topic, *(category.aliases or [])]
                for candidate in candidates:
                    candidate_raw = str(candidate or "").strip().lower()
                    if candidate_raw and candidate_raw in raw:
                        return category.default_topic or category.name
        except Exception:
            pass

        if any(keyword in raw for keyword in ["khiếu nại", "khieu nai", "phàn nàn", "phan nan"]):
            return "khiếu nại"

        if any(keyword in raw for keyword in ["tin báo tội phạm", "toi pham", "tội phạm", "vi phạm", "vi pham", "crime"]):
            return "tin báo tội phạm"

        if any(keyword in raw for keyword in ["thủ tục hành chính", "thu tuc", "hành chính", "hanh chinh", "hồ sơ", "ho so"]):
            return "thủ tục hành chính"

        if any(keyword in raw for keyword in ["hỗ trợ kỹ thuật", "ho tro ky thuat", "lỗi", "loi", "technical"]):
            return "hỗ trợ kỹ thuật"

        if any(keyword in raw for keyword in ["hỏi giá", "hoi gia", "báo giá", "bao gia"]):
            return "hỏi giá"

        return raw or "khác"

    def _normalize_sentiment(self, sentiment: Any) -> str:
        raw = str(sentiment or "").strip().lower()

        mapping = {
            "positive": "tích cực",
            "neutral": "trung lập",
            "negative": "tiêu cực",
            "tich cuc": "tích cực",
            "trung lap": "trung lập",
            "tieu cuc": "tiêu cực",
        }

        normalized = mapping.get(raw, raw)
        if normalized not in self.ALLOWED_SENTIMENTS:
            return "trung lập"
        return normalized

    def _normalize_priority(self, priority: Any) -> str:
        raw = str(priority or "").strip().lower()

        mapping = {
            "medium": "normal",
            "urgent": "high",
            "critical": "high",
        }

        normalized = mapping.get(raw, raw)
        if normalized not in self.ALLOWED_PRIORITIES:
            return "normal"
        return normalized

    def _fallback_analysis(self, content: str) -> Dict[str, Any]:
        normalized = (content or "").strip().lower()

        topic = "khác"
        sentiment = "trung lập"
        priority = "normal"
        summary = f"Nội dung người dân gửi: {content[:500]}"

        if any(keyword in normalized for keyword in [
            "khiếu nại", "khieu nai", "phàn nàn", "phan nan", "bức xúc", "buc xuc"
        ]):
            topic = "khiếu nại"
            sentiment = "tiêu cực"
            priority = "high"

        elif any(keyword in normalized for keyword in [
            "tội phạm", "toi pham", "trộm", "trom", "cướp", "cuop",
            "đánh nhau", "danh nhau", "đe dọa", "de doa", "ma túy", "ma tuy"
        ]):
            topic = "tin báo tội phạm"
            sentiment = "tiêu cực"
            priority = "high"

        elif any(keyword in normalized for keyword in [
            "thủ tục", "thu tuc", "hồ sơ", "ho so", "đăng ký", "dang ky",
            "xác nhận", "xac nhan", "cấp giấy", "cap giay"
        ]):
            topic = "thủ tục hành chính"
            sentiment = "trung lập"
            priority = "normal"

        elif any(keyword in normalized for keyword in [
            "lỗi", "loi", "không được", "khong duoc", "không vào được",
            "khong vao duoc", "không đăng ký", "khong dang ky"
        ]):
            topic = "hỗ trợ kỹ thuật"
            sentiment = "tiêu cực"
            priority = "high"

        elif any(keyword in normalized for keyword in ["giá", "bao nhiêu", "báo giá", "bao gia"]):
            topic = "hỏi giá"
            sentiment = "trung lập"
            priority = "normal"

        elif any(keyword in normalized for keyword in ["cảm ơn", "cam on", "ok", "được rồi", "duoc roi"]):
            topic = "phản hồi tích cực"
            sentiment = "tích cực"
            priority = "low"

        return {
            "topic": topic,
            "sentiment": sentiment,
            "priority": priority,
            "summary": summary,
            "engine": "stub",
            "raw_result": {
                "normalized_content": normalized,
                "matched_by": "keyword_rules_v2",
            },
        }