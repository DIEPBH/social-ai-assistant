import json
import os
import re
from datetime import datetime
from typing import Any, Dict

import requests
from django.utils import timezone


class AdminAIInterpreter:
    ALLOWED_COMMANDS = {
        "today_insight",
        "system_status",
        "generate_daily_report",
        "generate_custom_report",
        "list_submissions",
        "submission_detail",
        "unknown",
    }

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.timeout = int(os.getenv("GEMINI_TIMEOUT", "30"))
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={self.api_key}"

    def interpret(self, content: str) -> Dict[str, Any]:
        text = (content or "").strip()

        if not text:
            return self._not_command("empty_content")

        try:
            return self._call_gemini(text)
        except Exception as exc:
            return {
                "is_command": False,
                "command_type": None,
                "source": "ai",
                "reason": "ai_interpreter_failed",
                "error": str(exc),
            }

    def _call_gemini(self, text: str) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("Missing GEMINI_API_KEY")

        now = timezone.localtime()
        prompt = (
            "Bạn là bộ phân loại lệnh quản trị cho hệ thống Zalo OA. "
            "Chỉ trả về DUY NHẤT một JSON hợp lệ. Không giải thích thêm.\n\n"
            "Các command_type được phép:\n"
            "- today_insight: admin muốn xem tình hình/tổng quan hôm nay.\n"
            "- system_status: admin muốn kiểm tra hệ thống có lỗi không.\n"
            "- generate_daily_report: admin muốn tạo báo cáo cho một ngày cụ thể.\n"
            "- generate_custom_report: admin muốn tạo báo cáo cho tuần này hoặc tháng này.\n"
            "- list_submissions: admin/chuyên viên muốn xem danh sách các hồ sơ tiếp nhận hoặc hồ sơ được giao.\n"
            "- submission_detail: admin/chuyên viên muốn xem chi tiết một hồ sơ cụ thể theo ID.\n"
            "- unknown: không hiểu hoặc không phải lệnh quản trị.\n\n"
            "JSON bắt buộc có dạng:\n"
            "{"
            "\"is_command\": true/false, "
            "\"command_type\": \"...\", "
            "\"submission_id\": 123 hoặc null, "
            "\"filter_type\": \"default|unassigned|pending|in_progress|today|yesterday|urgent|specific_date\", "
            "\"date_type\": \"today|yesterday|specific|none\", "
            "\"date\": \"YYYY-MM-DD hoặc null\", "
            "\"range\": \"this_week|this_month|none\", "
            "\"confidence\": 0.0"
            "}\n\n"
            "Quy tắc:\n"
            "- Nếu hỏi tình hình, tổng quan, hôm nay có gì nổi bật: today_insight.\n"
            "- Nếu hỏi hệ thống ổn không, có lỗi không, kiểm tra hệ thống: system_status.\n"
            "- Nếu yêu cầu xem danh sách hồ sơ: list_submissions. Xác định filter_type:\n"
            "  + 'chưa phân công': filter_type=unassigned\n"
            "  + 'chưa xử lý': filter_type=pending\n"
            "  + 'đang xử lý': filter_type=in_progress\n"
            "  + 'hôm nay': filter_type=today\n"
            "  + 'hôm qua': filter_type=yesterday\n"
            "  + 'khẩn cấp' / 'ưu tiên': filter_type=urgent\n"
            "  + ngày cụ thể: filter_type=specific_date, date=YYYY-MM-DD\n"
            "  + danh sách chung: filter_type=default\n"
            "- Nếu yêu cầu xem hồ sơ cụ thể theo mã/ID (ví dụ 'xem hồ sơ 114', 'chi tiết hồ sơ 99'): submission_detail, submission_id=mã số.\n"
            "- Nếu yêu cầu báo cáo hôm nay: generate_daily_report, date_type=today.\n"
            "- Nếu yêu cầu báo cáo hôm qua: generate_daily_report, date_type=yesterday.\n"
            "- Nếu yêu cầu báo cáo ngày cụ thể: generate_daily_report, date_type=specific, date=YYYY-MM-DD.\n"
            "- Nếu yêu cầu báo cáo tuần này: generate_custom_report, range=this_week.\n"
            "- Nếu yêu cầu báo cáo tháng này: generate_custom_report, range=this_month.\n"
            "- Nếu không chắc chắn thì unknown.\n\n"
            f"Hôm nay là {now.strftime('%Y-%m-%d')}.\n"
            f"Lệnh admin cần phân loại:\n{text}"
        )

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0
            }
        }

        response = requests.post(self.url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        if data and "candidates" in data and len(data["candidates"]) > 0:
            message_content = data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            raise RuntimeError("No candidates found in Gemini response")

        parsed = self._parse_json(message_content)
        return self._normalize_result(parsed, raw_response=data)

    def _parse_json(self, content: str) -> Dict[str, Any]:
        content = (content or "").strip()

        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if fenced_match:
            parsed = json.loads(fenced_match.group(1))
            if isinstance(parsed, dict):
                return parsed

        object_match = re.search(r"(\{.*\})", content, re.DOTALL)
        if object_match:
            parsed = json.loads(object_match.group(1))
            if isinstance(parsed, dict):
                return parsed

        raise ValueError(f"Invalid AI JSON: {content}")

    def _normalize_result(self, parsed: Dict[str, Any], raw_response=None) -> Dict[str, Any]:
        command_type = str(parsed.get("command_type") or "unknown").strip()

        if command_type not in self.ALLOWED_COMMANDS:
            command_type = "unknown"

        is_command = bool(parsed.get("is_command")) and command_type != "unknown"

        sub_id = parsed.get("submission_id")
        try:
            sub_id = int(sub_id) if sub_id is not None else None
        except (ValueError, TypeError):
            sub_id = None

        filter_type = str(parsed.get("filter_type") or "default").strip()
        target_date = None
        if parsed.get("date"):
            try:
                target_date = datetime.strptime(parsed.get("date"), "%Y-%m-%d").date()
            except Exception:
                pass

        return {
            "is_command": is_command,
            "command_type": command_type if is_command else None,
            "submission_id": sub_id,
            "filter_type": filter_type,
            "target_date": target_date,
            "date_type": parsed.get("date_type") or "none",
            "date": parsed.get("date"),
            "range": parsed.get("range") or "none",
            "confidence": parsed.get("confidence", 0),
            "source": "ai",
            "raw_ai_result": parsed,
        }

    def _not_command(self, reason: str) -> Dict[str, Any]:
        return {
            "is_command": False,
            "command_type": None,
            "source": "ai",
            "reason": reason,
        }