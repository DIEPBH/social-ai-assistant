from django.contrib import admin
from django.utils.html import format_html

from .models import (
    AdminCommand,
    AdminCommandPattern,
    Channel,
    Conversation,
    IntakeCategory,
    IntakeSubmission,
    IntakeTemplate,
    IntakeTemplateField,
    IntegrationLog,
    IntakeValidationRule,
    KeywordRule,
    Message,
    Report,
)


def badge(label, color="secondary"):
    return format_html(
        '<span class="badge badge-{}" style="font-size: 12px;">{}</span>',
        color,
        label or "-"
    )


class IntakeTemplateFieldInline(admin.TabularInline):
    model = IntakeTemplateField
    extra = 1
    fields = (
        "order",
        "label",
        "field_key",
        "target_field",
        "field_type",
        "match_condition",
        "is_required",
        "aliases",
        "help_text",
        "is_active",
    )

@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "system",
        "direction",
        "endpoint",
        "method",
        "status_code",
        "processing_time_ms",
        "created_at",
    )
    search_fields = ("endpoint", "request_payload", "response_payload", "error_message")
    list_filter = ("system", "direction", "status_code", "created_at")
    ordering = ("-created_at",)
    readonly_fields = (
        "system",
        "direction",
        "endpoint",
        "method",
        "status_code",
        "request_payload",
        "response_payload",
        "error_message",
        "processing_time_ms",
        "created_at",
    )

@admin.register(IntakeCategory)
class IntakeCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "selection_value",
        "name",
        "code",
        "menu_order",
        "default_priority",
        "requires_human_review",
        "is_active",
    )
    search_fields = ("code", "name", "description")
    list_filter = ("is_active", "default_priority", "requires_human_review")
    ordering = ("menu_order", "id")
    fieldsets = (
        ("Thông tin menu", {
            "fields": ("name", "code", "selection_value", "aliases", "description", "menu_order", "is_active")
        }),
        ("Phân tích và xử lý mặc định", {
            "fields": (
                "default_topic",
                "default_sentiment",
                "default_priority",
                "default_department",
                "requires_human_review",
            )
        }),
        ("Phản hồi", {
            "fields": ("success_reply_text", "urgent_reply_text")
        }),
    )


@admin.register(IntakeTemplate)
class IntakeTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "title", "is_active", "updated_at")
    search_fields = ("title", "category__name", "category__code")
    list_filter = ("is_active", "category")
    inlines = [IntakeTemplateFieldInline]


@admin.register(IntakeTemplateField)
class IntakeTemplateFieldAdmin(admin.ModelAdmin):
    list_display = ("id", "template", "order", "label", "field_key", "target_field", "match_condition", "is_required", "is_active")
    search_fields = ("label", "field_key", "template__category__name")
    list_filter = ("is_active", "is_required", "match_condition", "target_field", "field_type", "template__category")
    ordering = ("template__category__menu_order", "template", "order")


@admin.register(IntakeValidationRule)
class IntakeValidationRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "rule_type", "order", "is_active")
    search_fields = ("name", "error_message")
    list_filter = ("is_active", "rule_type", "category")
    ordering = ("order", "id")


@admin.register(KeywordRule)
class KeywordRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "match_type", "topic", "priority", "order", "is_active")
    search_fields = ("name", "topic", "keywords", "pattern")
    list_filter = ("is_active", "match_type", "priority", "category")
    ordering = ("order", "id")


class AdminCommandPatternInline(admin.TabularInline):
    model = AdminCommandPattern
    extra = 1
    fields = ("priority", "match_type", "pattern_text", "is_active")


@admin.register(AdminCommand)
class AdminCommandAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "action", "report_period", "order", "is_active")
    search_fields = ("name", "code", "help_text")
    list_filter = ("is_active", "action", "report_period")
    ordering = ("order", "id")
    inlines = [AdminCommandPatternInline]
    fieldsets = (
        ("Thông tin lệnh", {
            "fields": ("name", "code", "action", "help_text", "order", "is_active")
        }),
        ("Nếu là lệnh báo cáo", {
            "fields": ("report_period", "report_type", "report_title_template")
        }),
        ("Nếu là lệnh trả lời cố định", {
            "fields": ("static_reply_text",)
        }),
    )


@admin.register(AdminCommandPattern)
class AdminCommandPatternAdmin(admin.ModelAdmin):
    list_display = ("id", "command", "match_type", "short_pattern", "priority", "is_active")
    search_fields = ("pattern_text", "command__name", "command__code")
    list_filter = ("is_active", "match_type", "command")
    ordering = ("priority", "id")

    @admin.display(description="Mẫu câu")
    def short_pattern(self, obj):
        text = obj.pattern_text or ""
        return text[:80] + "..." if len(text) > 80 else text


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
        "current_category",
        "current_intent",
        "form_retry_count",
        "updated_at",
    )
    search_fields = ("customer_id", "customer_name", "channel__name", "current_category__name")
    list_filter = ("status", "channel", "current_state", "current_category")

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
            "custom": "secondary",
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
        "category_badge",
        "citizen_name",
        "phone_number",
        "status_badge",
        "priority",
        "created_at",
    )
    search_fields = ("citizen_name", "phone_number", "content", "category__name", "intent")
    list_filter = ("category", "intent", "status", "priority", "created_at")
    readonly_fields = ("raw_extracted_data", "created_at")

    @admin.display(description="Loại phản ánh")
    def category_badge(self, obj):
        color_map = {
            "complaint": "warning",
            "crime_report": "danger",
            "admin_procedure": "info",
        }
        label = obj.category.name if obj.category else obj.intent
        code = obj.category.code if obj.category else obj.intent
        return badge(label, color_map.get(code, "secondary"))

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
