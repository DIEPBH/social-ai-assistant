import re
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
                return self._build_command_result(pattern.command, match, content)

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
                "tình hình hôm nay",
                "báo cáo hôm nay",
                "hệ thống có lỗi không",
            ]

        return "Tôi chưa hiểu lệnh quản trị này.\nAnh/chị có thể thử:\n" + "\n".join(
            f"- {item}" for item in suggestions
        )

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

    def _build_command_result(self, command, match, content):
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
        value = unicodedata.normalize("NFD", value)
        value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
        value = re.sub(r"[^a-z0-9\s_\-/]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value
