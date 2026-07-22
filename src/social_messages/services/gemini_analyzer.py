import os
import json
import logging
import requests
from typing import Any, Dict

logger = logging.getLogger(__name__)

class GeminiAnalyzer:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.timeout = 60

    def _get_models(self) -> list:
        try:
            from social_messages.models import SystemConfig
            config = SystemConfig.objects.filter(key="GEMINI_MODELS", is_active=True).first()
            if config and config.value:
                return [m.strip() for m in config.value.split(",") if m.strip()]
        except Exception:
            pass
        return ["gemini-3.5-flash"]

    def _call_api(self, prompt: str, json_response: bool = True) -> Any:
        if not self.api_key:
            logger.error("Missing GEMINI_API_KEY environment variable")
            raise RuntimeError("Missing GEMINI_API_KEY")

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1
            }
        }
        if json_response:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        import time
        from social_messages.models import IntegrationLog
        
        models = self._get_models()
        error_msg = ""
        response = None
        data = None
        success = False

        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            start_time = time.time()
            try:
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        logger.info("Calling Gemini API directly with model %s, attempt %d", model, attempt + 1)
                        response = requests.post(url, json=payload, timeout=self.timeout)
                        if response.status_code != 200:
                            logger.error("Gemini API Error Response: %s", response.text)
                        response.raise_for_status()
                        data = response.json()
                        error_msg = ""
                        success = True
                        break
                    except requests.exceptions.RequestException as e:
                        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None and e.response.status_code == 429:
                            error_msg = f"Quota exceeded for model {model}"
                            logger.warning(error_msg)
                            break # try next model
                            
                        should_retry = isinstance(e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError))
                        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None and e.response.status_code >= 500:
                            should_retry = True
                            
                        if should_retry:
                            logger.warning("Gemini API transient error (attempt %d): %s", attempt + 1, str(e))
                            if attempt == max_retries - 1:
                                error_msg = str(e)
                                logger.exception("Error calling Gemini API (Transient): %s", e)
                            else:
                                time.sleep(2 ** attempt)
                        else:
                            error_msg = str(e)
                            logger.exception("Error calling Gemini API (Fatal): %s", e)
                            break # try next model
                    except Exception as e:
                        error_msg = str(e)
                        logger.exception("Error calling Gemini API: %s", e)
                        break # try next model
            finally:
                processing_time_ms = (time.time() - start_time) * 1000
                resp_json = {}
                if response:
                    try:
                        resp_json = response.json()
                    except Exception:
                        resp_json = {"raw_text": response.text}
                
                safe_url = url.split("?key=")[0] if "?key=" in url else url
                IntegrationLog.objects.create(
                    system=f"gemini_api_{model}",
                    direction="outbound",
                    endpoint=safe_url,
                    method="POST",
                    status_code=response.status_code if response else None,
                    request_payload=payload,
                    response_payload=resp_json,
                    error_message=error_msg,
                    processing_time_ms=processing_time_ms
                )
            
            if success:
                break

        if not success:
            raise RuntimeError(f"Gemini API Error after trying all models: {error_msg}")

        if data and "candidates" in data and len(data["candidates"]) > 0:
            content_text = data["candidates"][0]["content"]["parts"][0]["text"]
            if json_response:
                return self._parse_json_response(content_text)
            return content_text.strip()
        else:
            logger.error("Gemini API returned unexpected format: %s", data)
            raise RuntimeError("No candidates found in Gemini response")

    def analyze_message(self, content: str) -> Dict[str, Any]:
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
        return self._call_api(prompt, json_response=True)

    def extract_entities(self, text: str, fields: list) -> Dict[str, str]:
        fields_desc = []
        for f in fields:
            fields_desc.append(f"- {f.field_key}: {f.label} ({f.help_text or 'Không có ghi chú'})")
        fields_str = "\n".join(fields_desc)
        
        prompt = (
            "Bạn là một trợ lý AI thông minh làm nhiệm vụ rút trích dữ liệu từ tin nhắn của người dân.\n"
            "Người dân có thể gửi nhiều tin nhắn được nối với nhau, hoặc gửi một đoạn văn dài. "
            "Nhiệm vụ của bạn là lấy thông tin và điền vào các trường tương ứng dưới dạng JSON.\n"
            "Danh sách các trường cần trích xuất (nếu không có thông tin trong tin nhắn thì để chuỗi rỗng ''):\n"
            f"{fields_str}\n\n"
            "Hãy phân tích nội dung sau và trả về DUY NHẤT một JSON hợp lệ, các khóa trong JSON phải là các field_key ở trên.\n\n"
            f"Nội dung người dân gửi:\n{text}"
        )
        return self._call_api(prompt, json_response=True)

    def generate_followup_question(self, user_text: str, missing_fields: list, category_name: str) -> str:
        missing_str = ", ".join(missing_fields)
        prompt = (
            "Bạn là một tổng đài viên AI lịch sự và thân thiện của nhà nước, phụ trách tiếp nhận phản ánh về mảng: " f"{category_name}.\n"
            "Hệ thống đã nhận thông tin từ người dân nhưng vẫn CÒN THIẾU các thông tin quan trọng sau: " f"{missing_str}.\n\n"
            "Dựa trên nội dung người dân đã gửi:\n"
            f"\"{user_text}\"\n\n"
            "Hãy viết MỘT câu trả lời ngắn gọn (dưới 40 chữ), xác nhận đã nhận thông tin và nhẹ nhàng yêu cầu người dân bổ sung thêm các thông tin còn thiếu. "
            "Không thêm các từ thừa như 'Dạ' ở đầu câu một cách máy móc nếu không cần thiết, tự nhiên như người bình thường nhắn tin."
        )
        return self._call_api(prompt, json_response=False)

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
            
            return json.loads(text)
        except Exception as e:
            logger.error("Failed to parse JSON from Gemini: %s. Raw text: %s", e, text)
            return {}
