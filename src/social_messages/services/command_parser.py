from datetime import datetime, time
from django.utils import timezone


class CommandParser:
    def parse(self, content: str) -> dict:
        normalized = (content or "").strip().lower()

        if any(keyword in normalized for keyword in ["báo cáo hôm nay", "bao cao hom nay", "report today"]):
            now = timezone.localtime()
            from_time = timezone.make_aware(datetime.combine(now.date(), time.min))
            to_time = timezone.make_aware(datetime.combine(now.date(), time.max))

            return {
                "is_command": True,
                "command_type": "generate_daily_report",
                "title": f"Báo cáo ngày {now.strftime('%d-%m-%Y')}",
                "from_time": from_time,
                "to_time": to_time,
                "report_type": "daily",
            }

        if any(keyword in normalized for keyword in ["báo cáo hôm qua", "bao cao hom qua", "report yesterday"]):
            now = timezone.localtime()
            target_date = now.date() - timezone.timedelta(days=1)
            from_time = timezone.make_aware(datetime.combine(target_date, time.min))
            to_time = timezone.make_aware(datetime.combine(target_date, time.max))

            return {
                "is_command": True,
                "command_type": "generate_daily_report",
                "title": f"Báo cáo ngày {target_date.strftime('%d-%m-%Y')}",
                "from_time": from_time,
                "to_time": to_time,
                "report_type": "daily",
            }

        return {
            "is_command": False,
            "command_type": None,
        }
