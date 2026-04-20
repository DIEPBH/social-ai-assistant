from collections import Counter
from pathlib import Path

from django.conf import settings
from openpyxl import Workbook

from social_messages.models import Message, MessageAnalysis, Report


class DailyReportExporter:
    def __init__(self, report: Report):
        self.report = report

    def export(self) -> str:
        workbook = Workbook()

        summary_sheet = workbook.active
        summary_sheet.title = "Tong_quan"

        detail_sheet = workbook.create_sheet("Chi_tiet_tin_nhan")
        analysis_sheet = workbook.create_sheet("Phan_tich_AI")

        messages = Message.objects.select_related(
            "conversation",
            "conversation__channel",
        ).filter(
            sent_at__gte=self.report.from_time,
            sent_at__lte=self.report.to_time,
        ).order_by("sent_at")

        analyses = MessageAnalysis.objects.select_related(
            "message",
            "message__conversation",
            "message__conversation__channel",
        ).filter(
            message__sent_at__gte=self.report.from_time,
            message__sent_at__lte=self.report.to_time,
        )

        total_messages = messages.count()
        total_conversations = messages.values("conversation_id").distinct().count()

        topic_counter = Counter()
        sentiment_counter = Counter()
        priority_counter = Counter()

        for analysis in analyses:
            if analysis.topic:
                topic_counter[analysis.topic] += 1
            if analysis.sentiment:
                sentiment_counter[analysis.sentiment] += 1
            if analysis.priority:
                priority_counter[analysis.priority] += 1

        summary_sheet.append(["Muc", "Gia_tri"])
        summary_sheet.append(["Tieu de bao cao", self.report.title])
        summary_sheet.append(["Tu thoi gian", self.report.from_time.strftime("%Y-%m-%d %H:%M:%S")])
        summary_sheet.append(["Den thoi gian", self.report.to_time.strftime("%Y-%m-%d %H:%M:%S")])
        summary_sheet.append(["Tong so tin nhan", total_messages])
        summary_sheet.append(["Tong so hoi thoai", total_conversations])
        summary_sheet.append([])

        summary_sheet.append(["Thong ke theo chu de", "So luong"])
        for topic, count in topic_counter.most_common():
            summary_sheet.append([topic, count])

        summary_sheet.append([])
        summary_sheet.append(["Thong ke theo cam xuc", "So luong"])
        for sentiment, count in sentiment_counter.most_common():
            summary_sheet.append([sentiment, count])

        summary_sheet.append([])
        summary_sheet.append(["Thong ke theo muc uu tien", "So luong"])
        for priority, count in priority_counter.most_common():
            summary_sheet.append([priority, count])

        detail_sheet.append([
            "Message ID",
            "Platform",
            "Channel",
            "Customer ID",
            "Customer Name",
            "Sender Type",
            "Message Type",
            "Content",
            "Sent At",
        ])

        for message in messages:
            detail_sheet.append([
                message.platform_message_id,
                message.conversation.channel.platform,
                message.conversation.channel.name,
                message.conversation.customer_id,
                message.conversation.customer_name,
                message.sender_type,
                message.message_type,
                message.content,
                message.sent_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])

        analysis_sheet.append([
            "Message ID",
            "Platform",
            "Customer Name",
            "Topic",
            "Sentiment",
            "Priority",
            "Summary",
            "Status",
            "Processed At",
        ])

        for analysis in analyses.order_by("message__sent_at"):
            analysis_sheet.append([
                analysis.message.platform_message_id,
                analysis.message.conversation.channel.platform,
                analysis.message.conversation.customer_name,
                analysis.topic,
                analysis.sentiment,
                analysis.priority,
                analysis.summary,
                analysis.status,
                analysis.processed_at.strftime("%Y-%m-%d %H:%M:%S") if analysis.processed_at else "",
            ])

        reports_dir = Path(settings.MEDIA_ROOT) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        filename = f"daily_report_{self.report.id}.xlsx"
        file_path = reports_dir / filename

        workbook.save(file_path)

        return str(file_path)
