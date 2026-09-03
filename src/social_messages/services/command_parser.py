import re
from typing import Optional
import unicodedata
from datetime import datetime, time, timedelta

from django.utils import timezone

from social_messages.models import AdminCommandPattern


class CommandParser:
    def parse(self, content: str) -> dict:
        normalized = self._normalize(content)

        if not normalized:
            return self._not_command()

        patterns = AdminCommandPattern.objects.select_related("command").filter(
            is_active=True,
            command__is_active=True,
        ).order_by("priority", "id")

        for pattern in patterns:
            match = self._match_pattern(pattern, content, normalized)
            if match:
                res = self._build_command_result(pattern.command, match, content, normalized)
                if res.get("is_command"):
                    return res

        # Fallback các lệnh hồ sơ mặc định nếu chưa cấu hình DB pattern
        builtin_result = self._check_builtin_submission_commands(content, normalized)
        if builtin_result.get("is_command"):
            return builtin_result

        return self._not_command()

    def get_help_text(self):
        patterns = AdminCommandPattern.objects.select_related("command").filter(
            is_active=True,
            command__is_active=True,
        ).order_by("command__order", "priority")[:5]

        suggestions = []
        for pattern in patterns:
            help_text = pattern.command.help_text or pattern.pattern_text
            if help_text and help_text not in suggestions:
                suggestions.append(help_text)

        if not suggestions:
            suggestions = [
                "danh sách hồ sơ",
                "xem hồ sơ 114",
                "tình hình hôm nay",
                "báo cáo hôm nay",
                "hệ thống có lỗi không",
            ]

        return "Tôi chưa hiểu lệnh quản trị này.\nAnh/chị có thể thử:\n" + "\n".join(
            f"- {item}" for item in suggestions
        )

    def _check_builtin_submission_commands(self, original_content: str, normalized_content: str) -> dict:
        # 1. Lệnh xem chi tiết hồ sơ: xem ho so 114, ho so 114, hs 114, chi tiet ho so 114, hs#114
        detail_match = re.search(
            r"^(?:xem\s+)?(?:ho\s*so|chi\s*tiet\s*ho\s*so|hs)\s*#?(?P<submission_id>\d+)$",
            normalized_content,
        )
        if detail_match:
            try:
                sub_id = int(detail_match.group("submission_id"))
                return {
                    "is_command": True,
                    "command_type": "submission_detail",
                    "submission_id": sub_id,
                    "source": "builtin",
                }
            except (ValueError, IndexError):
                pass

        # 2. Lệnh xem hồ sơ theo ngày cụ thể: ho so ngay 02/09/2026, hs ngay 02-09-2026
        date_match = re.search(
            r"^(?:xem\s+)?(?:danh\s*sach\s+)?(?:ho\s*so|hs)\s+ngay\s+(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{4})$",
            normalized_content,
        )
        if date_match:
            try:
                d = datetime(
                    int(date_match.group("year")),
                    int(date_match.group("month")),
                    int(date_match.group("day")),
                ).date()
                return {
                    "is_command": True,
                    "command_type": "list_submissions",
                    "filter_type": "specific_date",
                    "target_date": d,
                    "source": "builtin",
                }
            except ValueError:
                pass

        # 3. Lọc theo trạng thái và thời gian
        # 3.1 Chưa phân công
        if any(kw in normalized_content for kw in ["chua phan cong"]):
            return {
                "is_command": True,
                "command_type": "list_submissions",
                "filter_type": "unassigned",
                "source": "builtin",
            }

        # 3.2 Chưa xử lý
        if any(kw in normalized_content for kw in ["chua xu ly", "cho xu ly"]):
            return {
                "is_command": True,
                "command_type": "list_submissions",
                "filter_type": "pending",
                "source": "builtin",
            }

        # 3.3 Đang xử lý
        if any(kw in normalized_content for kw in ["dang xu ly"]):
            return {
                "is_command": True,
                "command_type": "list_submissions",
                "filter_type": "in_progress",
                "source": "builtin",
            }

        # 3.4 Hôm nay
        if any(kw in normalized_content for kw in ["ho so hom nay", "hs hom nay", "danh sach ho so hom nay"]):
            return {
                "is_command": True,
                "command_type": "list_submissions",
                "filter_type": "today",
                "source": "builtin",
            }

        # 3.5 Hôm qua
        if any(kw in normalized_content for kw in ["ho so hom qua", "hs hom qua", "danh sach ho so hom qua"]):
            return {
                "is_command": True,
                "command_type": "list_submissions",
                "filter_type": "yesterday",
                "source": "builtin",
            }

        # 3.6 Khẩn cấp / Ưu tiên
        if any(kw in normalized_content for kw in ["khan cap", "ho so uu tien", "hs uu tien"]):
            return {
                "is_command": True,
                "command_type": "list_submissions",
                "filter_type": "urgent",
                "source": "builtin",
            }

        # 4. Lệnh mặc định xem danh sách
        list_phrases = {
            "danh sach ho so",
            "tat ca ho so",
            "ho so cua toi",
            "cac ho so",
            "ds ho so",
            "dshs",
            "ho so",
            "xem danh sach ho so",
            "xem tat ca ho so",
        }
        if normalized_content in list_phrases:
            return {
                "is_command": True,
                "command_type": "list_submissions",
                "filter_type": "default",
                "source": "builtin",
            }

        return self._not_command()

    def _extract_submission_id_from_match(self, match, content: str) -> Optional[int]:
        if hasattr(match, "groupdict") and "submission_id" in match.groupdict():
            try:
                return int(match.groupdict()["submission_id"])
            except (ValueError, TypeError):
                pass
        
        digits = re.search(r"#?(\d+)", content or "")
        if digits:
            try:
                return int(digits.group(1))
            except (ValueError, TypeError):
                pass
        return None

    def _match_pattern(self, pattern, original_content, normalized_content):
        pattern_text = pattern.pattern_text or ""
        normalized_pattern = self._normalize(pattern_text)

        if pattern.match_type == "exact":
            return True if normalized_content == normalized_pattern else None

        if pattern.match_type == "contains":
            return True if normalized_pattern and normalized_pattern in normalized_content else None

        if pattern.match_type == "regex":
            try:
                return re.search(pattern_text, original_content or "", flags=re.IGNORECASE | re.UNICODE)
            except re.error:
                return None

        return None

    def _build_command_result(self, command, match, content, normalized_content=""):
        if command.action == "today_insight":
            return {
                "is_command": True,
                "command_type": "today_insight",
                "admin_command_id": command.id,
                "source": "db_pattern",
            }

        if command.action == "system_status":
            return {
                "is_command": True,
                "command_type": "system_status",
                "admin_command_id": command.id,
                "source": "db_pattern",
            }

        if command.action == "static_reply":
            return {
                "is_command": True,
                "command_type": "static_reply",
                "admin_command_id": command.id,
                "reply_text": command.static_reply_text,
                "source": "db_pattern",
            }

        if command.action == "generate_report":
            return self._build_report_command(command, match, content)

        if command.action == "list_submissions":
            filter_type = "default"
            target_date = None
            norm = normalized_content or self._normalize(content)

            if "chua phan cong" in norm:
                filter_type = "unassigned"
            elif "chua xu ly" in norm or "cho xu ly" in norm:
                filter_type = "pending"
            elif "dang xu ly" in norm:
                filter_type = "in_progress"
            elif "hom nay" in norm:
                filter_type = "today"
            elif "hom qua" in norm:
                filter_type = "yesterday"
            elif "khan cap" in norm or "uu tien" in norm:
                filter_type = "urgent"
            else:
                date_match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", content or "")
                if date_match:
                    try:
                        target_date = datetime(int(date_match.group(3)), int(date_match.group(2)), int(date_match.group(1))).date()
                        filter_type = "specific_date"
                    except ValueError:
                        pass

            return {
                "is_command": True,
                "command_type": "list_submissions",
                "filter_type": filter_type,
                "target_date": target_date,
                "admin_command_id": command.id,
                "source": "db_pattern",
            }

        if command.action == "submission_detail":
            sub_id = self._extract_submission_id_from_match(match, content)
            if not sub_id:
                return self._not_command()
            return {
                "is_command": True,
                "command_type": "submission_detail",
                "submission_id": sub_id,
                "admin_command_id": command.id,
                "source": "db_pattern",
            }

        return self._not_command()

    def _build_report_command(self, command, match, content):
        now = timezone.localtime()
        period = command.report_period

        if period == "today":
            target_date = now.date()
            return self._build_daily_report(command, target_date)

        if period == "yesterday":
            target_date = now.date() - timedelta(days=1)
            return self._build_daily_report(command, target_date)

        if period == "current_week":
            start_date = now.date() - timedelta(days=now.weekday())
            end_date = start_date + timedelta(days=6)
            title = command.report_title_template or "Báo cáo tuần {from_date} đến {to_date}"
            return self._build_custom_report(command, title, start_date, end_date)

        if period == "current_month":
            start_date = now.date().replace(day=1)
            if now.month == 12:
                next_month = now.date().replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.date().replace(month=now.month + 1, day=1)
            end_date = next_month - timedelta(days=1)
            title = command.report_title_template or "Báo cáo tháng {month_year}"
            return self._build_custom_report(command, title, start_date, end_date)

        if period == "specific_date":
            target_date = self._extract_date_from_match(match, content)
            if not target_date:
                return {
                    "is_command": True,
                    "command_type": "invalid_report_date",
                    "error": "Ngày báo cáo không hợp lệ",
                    "admin_command_id": command.id,
                    "source": "db_pattern",
                }
            return self._build_daily_report(command, target_date)

        return self._not_command()

    def _build_daily_report(self, command, target_date):
        title_template = command.report_title_template or "Báo cáo ngày {date}"
        title = title_template.format(
            date=target_date.strftime("%d-%m-%Y"),
            from_date=target_date.strftime("%d-%m-%Y"),
            to_date=target_date.strftime("%d-%m-%Y"),
            month_year=target_date.strftime("%m-%Y"),
        )
        return {
            "is_command": True,
            "command_type": "generate_daily_report",
            "title": title,
            "from_time": self._start_of_day(target_date),
            "to_time": self._end_of_day(target_date),
            "report_type": command.report_type or "daily",
            "admin_command_id": command.id,
            "source": "db_pattern",
        }

    def _build_custom_report(self, command, title_template, start_date, end_date):
        title = title_template.format(
            date=start_date.strftime("%d-%m-%Y"),
            from_date=start_date.strftime("%d-%m-%Y"),
            to_date=end_date.strftime("%d-%m-%Y"),
            month_year=start_date.strftime("%m-%Y"),
        )
        return {
            "is_command": True,
            "command_type": "generate_daily_report",
            "title": title,
            "from_time": self._start_of_day(start_date),
            "to_time": self._end_of_day(end_date),
            "report_type": command.report_type or "custom",
            "admin_command_id": command.id,
            "source": "db_pattern",
        }

    def _extract_date_from_match(self, match, content):
        if hasattr(match, "groupdict"):
            groups = match.groupdict()
            try:
                if groups.get("day") and groups.get("month") and groups.get("year"):
                    return datetime(
                        int(groups["year"]),
                        int(groups["month"]),
                        int(groups["day"]),
                    ).date()
            except ValueError:
                return None

        fallback = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", content or "")
        if fallback:
            try:
                return datetime(int(fallback.group(3)), int(fallback.group(2)), int(fallback.group(1))).date()
            except ValueError:
                return None

        return None

    def _start_of_day(self, target_date):
        return timezone.make_aware(datetime.combine(target_date, time.min))

    def _end_of_day(self, target_date):
        return timezone.make_aware(datetime.combine(target_date, time.max))

    def _not_command(self):
        return {
            "is_command": False,
            "command_type": None,
        }

    def _normalize(self, value: str) -> str:
        value = str(value or "").strip().lower()
        value = value.replace("đ", "d").replace("Đ", "d")
        value = unicodedata.normalize("NFD", value)
        value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
        value = re.sub(r"[^a-z0-9\s_\-/]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value
