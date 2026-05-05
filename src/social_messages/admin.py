from django.contrib import admin
from django.utils.html import format_html

from .models import Channel, Conversation, Message, MessageAnalysis, Report, IntakeSubmission


def badge(label, color="secondary"):
    return format_html(
        '<span class="badge badge-{}" style="font-size: 12px;">{}</span>',
        color,
        label or "-"
    )


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "platform_badge", "external_id", "is_active", "created_at")
    search_fields = ("name", "external_id")
    list_filter = ("platform", "is_active")

    @admin.display(description="Nền tảng")
    def platform_badge(self, obj):
        color_map = {
            "zalo": "primary",
            "facebook": "info",
            "web": "success",
        }
        return badge(obj.platform, color_map.get(obj.platform, "secondary"))


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "channel",
        "customer_id",
        "customer_name",
        "status_badge",
        "current_state",
        "current_intent",
        "form_retry_count",
        "updated_at",
    )
    search_fields = ("customer_id", "customer_name", "channel__name")
    list_filter = ("status", "channel")

    @admin.display(description="Trạng thái")
    def status_badge(self, obj):
        color_map = {
            "open": "success",
            "closed": "secondary",
            "pending": "warning",
        }
        return badge(getattr(obj, "status", "-"), color_map.get(getattr(obj, "status", ""), "secondary"))


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "platform_message_id",
        "sender_type_badge",
        "message_type",
        "short_content",
        "sent_at",
        "sender_id",
    )
    search_fields = ("platform_message_id", "sender_id", "content")
    list_filter = ("sender_type", "message_type", "conversation__channel")
    readonly_fields = ("platform_message_id", "raw_payload", "created_at")

    @admin.display(description="Người gửi")
    def sender_type_badge(self, obj):
        color_map = {
            "admin": "danger",
            "customer": "success",
            "system": "secondary",
            "bot": "info",
        }
        return badge(obj.sender_type, color_map.get(obj.sender_type, "secondary"))

    @admin.display(description="Nội dung")
    def short_content(self, obj):
        content = getattr(obj, "content", "") or ""
        return content[:80] + "..." if len(content) > 80 else content


@admin.register(MessageAnalysis)
class MessageAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "status_badge",
        "topic",
        "sentiment_badge",
        "priority_badge",
        "processed_at",
        "created_at",
    )
    search_fields = ("message__platform_message_id", "topic", "summary", "error_message")
    list_filter = ("status", "topic", "sentiment", "priority")

    @admin.display(description="Trạng thái")
    def status_badge(self, obj):
        color_map = {
            "pending": "warning",
            "processing": "info",
            "done": "success",
            "success": "success",
            "failed": "danger",
            "error": "danger",
        }
        return badge(obj.status, color_map.get(obj.status, "secondary"))

    @admin.display(description="Cảm xúc")
    def sentiment_badge(self, obj):
        color_map = {
            "tích cực": "success",
            "trung lập": "secondary",
            "tiêu cực": "danger",
            "positive": "success",
            "neutral": "secondary",
            "negative": "danger",
        }
        return badge(obj.sentiment, color_map.get(obj.sentiment, "secondary"))

    @admin.display(description="Ưu tiên")
    def priority_badge(self, obj):
        color_map = {
            "low": "secondary",
            "normal": "info",
            "medium": "info",
            "high": "warning",
            "urgent": "danger",
            "critical": "danger",
        }
        return badge(obj.priority, color_map.get(obj.priority, "secondary"))


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "report_type_badge",
        "status_badge",
        "from_time",
        "to_time",
        "file_name",
        "created_at",
        "completed_at",
    )
    search_fields = ("title", "file_name", "note")
    list_filter = ("report_type", "status")

    @admin.display(description="Loại báo cáo")
    def report_type_badge(self, obj):
        color_map = {
            "daily": "primary",
            "weekly": "info",
            "monthly": "success",
        }
        return badge(obj.report_type, color_map.get(obj.report_type, "secondary"))

    @admin.display(description="Trạng thái")
    def status_badge(self, obj):
        color_map = {
            "pending": "warning",
            "processing": "info",
            "completed": "success",
            "done": "success",
            "failed": "danger",
            "error": "danger",
        }
        return badge(obj.status, color_map.get(obj.status, "secondary"))


@admin.register(IntakeSubmission)
class IntakeSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "intent_badge",
        "citizen_name",
        "phone_number",
        "status_badge",
        "created_at",
    )
    search_fields = ("citizen_name", "phone_number", "content")
    list_filter = ("intent", "status", "created_at")

    @admin.display(description="Loại phản ánh")
    def intent_badge(self, obj):
        color_map = {
            "complaint": "warning",
            "crime_report": "danger",
            "admin_procedure": "info",
        }
        label = obj.get_intent_display() if hasattr(obj, "get_intent_display") else obj.intent
        return badge(label, color_map.get(obj.intent, "secondary"))

    @admin.display(description="Trạng thái")
    def status_badge(self, obj):
        color_map = {
            "received": "secondary",
            "validated": "info",
            "analyzed": "primary",
            "responded": "success",
            "rejected": "danger",
        }
        label = obj.get_status_display() if hasattr(obj, "get_status_display") else obj.status
        return badge(label, color_map.get(obj.status, "secondary"))