from collections import Counter
from datetime import datetime, time

from django.utils import timezone

from social_messages.models import IntakeSubmission, Message, Report


class AdminInsightService:
    def get_today_insight_text(self) -> str:
        now = timezone.localtime()
        start = timezone.make_aware(datetime.combine(now.date(), time.min))
        end = timezone.make_aware(datetime.combine(now.date(), time.max))

        submissions = IntakeSubmission.objects.select_related(
            "conversation",
            "conversation__channel",
        ).filter(
            created_at__gte=start,
            created_at__lte=end,
        )

        total = submissions.count()
        high_priority = submissions.filter(priority__in=["high", "urgent"]).count()
        responded = submissions.filter(status="responded").count()
        rejected = submissions.filter(status="rejected").count()

        intent_counter = Counter()
        topic_counter = Counter()
        platform_counter = Counter()

        for item in submissions:
            intent_counter[item.intent or "khác"] += 1
            topic_counter[item.topic or "chưa phân loại"] += 1

            if item.conversation and item.conversation.channel:
                platform_counter[item.conversation.channel.platform] += 1

        latest_messages = Message.objects.filter(
            created_at__gte=start,
            created_at__lte=end,
        ).exclude(
            sender_type="admin"
        ).count()

        latest_reports = Report.objects.filter(
            created_at__gte=start,
            created_at__lte=end,
        ).count()

        text = (
            "📊 Tình hình hôm nay\n"
            f"- Tổng tin nhắn người dân: {latest_messages}\n"
            f"- Tổng hồ sơ tiếp nhận: {total}\n"
            f"- Đã phản hồi: {responded}\n"
            f"- Không hợp lệ / bị từ chối: {rejected}\n"
            f"- Hồ sơ ưu tiên cao: {high_priority}\n"
            f"- Báo cáo đã tạo hôm nay: {latest_reports}\n"
        )

        if intent_counter:
            text += "\n📌 Theo loại hồ sơ:\n"
            for label, count in intent_counter.most_common(5):
                text += f"- {self._display_intent(label)}: {count}\n"

        if topic_counter:
            text += "\n🔥 Chủ đề nổi bật:\n"
            for label, count in topic_counter.most_common(5):
                text += f"- {label}: {count}\n"

        if platform_counter:
            text += "\n🌐 Theo nền tảng:\n"
            for label, count in platform_counter.most_common():
                text += f"- {self._display_platform(label)}: {count}\n"

        return text.strip()

    def get_system_status_text(self) -> str:
        now = timezone.localtime()

        pending_reports = Report.objects.filter(status="pending").count()
        processing_reports = Report.objects.filter(status="processing").count()
        failed_reports = Report.objects.filter(status="failed").count()

        rejected_submissions = IntakeSubmission.objects.filter(status="rejected").count()

        text = (
            "🛠 Trạng thái hệ thống\n"
            f"- Thời gian kiểm tra: {now.strftime('%d/%m/%Y %H:%M:%S')}\n"
            "- Webhook Zalo: đang nhận tin nếu anh/chị thấy phản hồi này\n"
            "- Celery worker: đang xử lý nếu phản hồi này được gửi từ task\n"
            f"- Báo cáo đang chờ: {pending_reports}\n"
            f"- Báo cáo đang xử lý: {processing_reports}\n"
            f"- Báo cáo lỗi: {failed_reports}\n"
            f"- Hồ sơ bị từ chối: {rejected_submissions}\n"
        )

        if failed_reports > 0:
            text += "\n⚠️ Có báo cáo lỗi. Nên kiểm tra log Celery và bảng Report trong admin."

        return text.strip()

    def _display_intent(self, intent: str) -> str:
        mapping = {
            "complaint": "Khiếu nại",
            "crime_report": "Tin báo tội phạm",
            "admin_procedure": "Hỏi thủ tục hành chính",
            "khác": "Khác",
        }
        return mapping.get(intent, intent or "Khác")

    def _display_platform(self, platform: str) -> str:
        mapping = {
            "zalo": "Zalo OA",
            "facebook": "Facebook Messenger",
        }
        return mapping.get(platform, platform or "Khác")