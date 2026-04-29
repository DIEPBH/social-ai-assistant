from django.contrib import admin

# Register your models here.
from .models import Channel, Conversation, Message, MessageAnalysis, Report, IntakeSubmission


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "platform", "external_id", "is_active", "created_at")
    search_fields = ("name", "external_id")
    list_filter = ("platform", "is_active")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "channel",
        "customer_id",
        "customer_name",
        "current_state",
        "current_intent",
        "form_retry_count",
        "updated_at",
    )
    search_fields = ("customer_id", "customer_name", "channel__name")
    list_filter = ("status", "channel")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "platform_message_id", "sender_type", "message_type", "sent_at","sender_id")
    search_fields = ("platform_message_id", "sender_id", "content")
    list_filter = ("sender_type", "message_type", "conversation__channel")

@admin.register(MessageAnalysis)
class MessageAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "status", "topic", "sentiment","result_payload", "priority", "processed_at", "created_at")
    search_fields = ("message__platform_message_id", "topic", "summary", "error_message")
    list_filter = ("status", "topic", "sentiment", "priority")

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "report_type", "status", "from_time", "to_time", "file_name", "created_at", "completed_at")
    search_fields = ("title", "file_name", "note")
    list_filter = ("report_type", "status")

@admin.register(IntakeSubmission)
class IntakeSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "intent",
        "citizen_name",
        "phone_number",
        "status",
        "created_at",
    )
    search_fields = ("citizen_name", "phone_number", "content")
    list_filter = ("intent", "status", "created_at")