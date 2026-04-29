import re
from datetime import datetime, time, timedelta

from django.utils import timezone


class CommandParser:
    def parse(self, content: str) -> dict:
        normalized = (content or "").strip().lower()

        if not normalized:
            return self._not_command()

        now = timezone.localtime()

        if any(k in normalized for k in [
            "báo cáo hôm nay",
            "bao cao hom nay",
            "báo cáo ngày hôm nay",
            "bao cao ngay hom nay",
            "report today",
        ]):
            return self._build_daily_report(now.date())

        if any(k in normalized for k in [
            "báo cáo hôm qua",
            "bao cao hom qua",
            "báo cáo ngày hôm qua",
            "bao cao ngay hom qua",
            "report yesterday",
        ]):
            return self._build_daily_report(now.date() - timedelta(days=1))

        if any(k in normalized for k in [
            "báo cáo tuần này",
            "bao cao tuan nay",
            "report this week",
        ]):
            start_date = now.date() - timedelta(days=now.weekday())
            end_date = start_date + timedelta(days=6)
            return self._build_custom_report(
                title=f"Báo cáo tuần {start_date.strftime('%d-%m-%Y')} đến {end_date.strftime('%d-%m-%Y')}",
                from_time=self._start_of_day(start_date),
                to_time=self._end_of_day(end_date),
            )

        if any(k in normalized for k in [
            "báo cáo tháng này",
            "bao cao thang nay",
            "report this month",
        ]):
            start_date = now.date().replace(day=1)

            if now.month == 12:
                next_month = now.date().replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.date().replace(month=now.month + 1, day=1)

            end_date = next_month - timedelta(days=1)

            return self._build_custom_report(
                title=f"Báo cáo tháng {now.strftime('%m-%Y')}",
                from_time=self._start_of_day(start_date),
                to_time=self._end_of_day(end_date),
            )

        match = re.search(r"báo cáo ngày\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})", normalized)
        if not match:
            match = re.search(r"bao cao ngay\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})", normalized)

        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))

            try:
                target_date = datetime(year, month, day).date()
            except ValueError:
                return {
                    "is_command": True,
                    "command_type": "invalid_report_date",
                    "error": "Ngày báo cáo không hợp lệ",
                }

            return self._build_daily_report(target_date)

        return self._not_command()

    def _build_daily_report(self, target_date):
        return {
            "is_command": True,
            "command_type": "generate_daily_report",
            "title": f"Báo cáo ngày {target_date.strftime('%d-%m-%Y')}",
            "from_time": self._start_of_day(target_date),
            "to_time": self._end_of_day(target_date),
            "report_type": "daily",
        }

    def _build_custom_report(self, title, from_time, to_time):
        return {
            "is_command": True,
            "command_type": "generate_daily_report",
            "title": title,
            "from_time": from_time,
            "to_time": to_time,
            "report_type": "custom",
        }

    def _start_of_day(self, target_date):
        return timezone.make_aware(datetime.combine(target_date, time.min))

    def _end_of_day(self, target_date):
        return timezone.make_aware(datetime.combine(target_date, time.max))

    def _not_command(self):
        return {
            "is_command": False,
            "command_type": None,
        }