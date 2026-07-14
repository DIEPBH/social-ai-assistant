from django.contrib import admin, messages
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.urls import path
from django.shortcuts import redirect, render

from .models import (
    AdminCommand,
    AdminCommandPattern,
    Channel,
    Conversation,
    IntakeCategory,
    IntakeSubmission,
    IntakeSubmissionAssignment,
    IntakeSubmissionHistory,
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


class IntakeSubmissionAssignmentFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        
        main_handler_count = 0
        assigned_users = set()
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
                
            user = form.cleaned_data.get('user')
            if user:
                if user.id in assigned_users:
                    raise ValidationError(f"Tài khoản '{user.username}' không được phép xuất hiện nhiều lần trong danh sách phân công.")
                assigned_users.add(user.id)
                
            role = form.cleaned_data.get('role')
            if role == 'main':
                main_handler_count += 1
                
        if main_handler_count > 1:
            raise ValidationError("Chỉ được phép có duy nhất 1 người xử lý chính.")

class IntakeSubmissionAssignmentInline(admin.TabularInline):
    model = IntakeSubmissionAssignment
    formset = IntakeSubmissionAssignmentFormSet
    extra = 1
    fields = ('user', 'role', 'status', 'return_reason', 'processing_note')
    
    def get_readonly_fields(self, request, obj=None):
        if request.user.groups.filter(name='Chuyên viên').exists() and not request.user.is_superuser:
            return self.fields
        return ('status', 'return_reason', 'processing_note')
        
    def has_change_permission(self, request, obj=None):
        if request.user.groups.filter(name='Chuyên viên').exists() and not request.user.is_superuser:
            return False
        if obj and obj.processing_status not in ['unassigned', 'returned']:
            return False
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request, obj):
        if request.user.groups.filter(name='Chuyên viên').exists() and not request.user.is_superuser:
            return False
        if obj and obj.processing_status not in ['unassigned', 'returned']:
            return False
        return super().has_add_permission(request, obj)
        
    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(name='Chuyên viên').exists() and not request.user.is_superuser:
            return False
        if obj and obj.processing_status not in ['unassigned', 'returned']:
            return False
        return super().has_delete_permission(request, obj)

class IntakeSubmissionHistoryInline(admin.TabularInline):
    model = IntakeSubmissionHistory
    extra = 0
    fields = ('created_at', 'user', 'action', 'note')
    readonly_fields = ('created_at', 'user', 'action', 'note')

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(IntakeSubmission)
class IntakeSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "category_badge",
        "citizen_name",
        "phone_number",
        "status_badge",
        "processing_status_badge",
        "priority",
        "created_at",
    )
    search_fields = ("citizen_name", "phone_number", "content", "category__name", "intent")
    list_filter = ("category", "intent", "status", "processing_status", "priority", "created_at")
    readonly_fields = ("raw_extracted_data", "created_at")
    inlines = [IntakeSubmissionAssignmentInline, IntakeSubmissionHistoryInline]
    change_form_template = "admin/social_messages/intakesubmission/change_form.html"

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id and request.user.groups.filter(name='Chuyên viên').exists() and not request.user.is_superuser:
            assignment = IntakeSubmissionAssignment.objects.filter(submission_id=object_id, user=request.user).order_by('-created_at').first()
            if assignment:
                extra_context['user_assignment'] = assignment
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.groups.filter(name='Quản trị viên').exists():
            return qs
        if request.user.groups.filter(name='Chuyên viên').exists():
            return qs.filter(assignments__user=request.user).distinct()
        return qs.none()

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            instance.save()
        formset.save_m2m()

        if formset.model == IntakeSubmissionAssignment:
            submission = form.instance
            has_assignments = submission.assignments.exists()
            if has_assignments and submission.processing_status in ['unassigned', 'returned']:
                submission.processing_status = 'pending'
                submission.save(update_fields=['processing_status'])
                
                # Reset assignments and create history
                for assignment in submission.assignments.all():
                    assignment.status = 'pending'
                    assignment.return_reason = ''
                    assignment.processing_note = ''
                    assignment.save(update_fields=['status', 'return_reason', 'processing_note'])
                    
                    IntakeSubmissionHistory.objects.create(
                        submission=submission,
                        user=assignment.user,
                        action='assign',
                        note=f"Phân công vai trò: {assignment.get_role_display()}"
                    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/action/<str:action_name>/",
                self.admin_site.admin_view(self.process_action_view),
                name="intakesubmission_action",
            ),
        ]
        return custom_urls + urls

    def process_action_view(self, request, object_id, action_name):
        obj = self.get_object(request, object_id)
        if not obj:
            return redirect("admin:social_messages_intakesubmission_changelist")

        assignment = IntakeSubmissionAssignment.objects.filter(submission=obj, user=request.user).order_by('-created_at').first()
        if not assignment:
            messages.error(request, "Bạn không được phân công xử lý hồ sơ này.")
            return redirect("admin:social_messages_intakesubmission_change", object_id)

        if request.method == "POST":
            if action_name == "accept":
                if assignment.role != "main":
                    messages.error(request, "Chỉ Người xử lý chính mới được phép Tiếp nhận hồ sơ.")
                    return redirect("admin:social_messages_intakesubmission_change", object_id)

                if obj.processing_status == "pending" and assignment.status == "pending":
                    obj.processing_status = "in_progress"
                    obj.save(update_fields=["processing_status"])
                    assignment.status = "in_progress"
                    assignment.save(update_fields=["status"])
                    
                    IntakeSubmissionHistory.objects.create(
                        submission=obj,
                        user=request.user,
                        action='accept',
                        note="Đã tiếp nhận hồ sơ để bắt đầu xử lý."
                    )
                    messages.success(request, "Đã tiếp nhận hồ sơ.")
                return redirect("admin:social_messages_intakesubmission_change", object_id)
            elif action_name == "return":
                if assignment.role == "co_handler" and obj.processing_status != "in_progress":
                    messages.error(request, "Người phối hợp chỉ được thao tác khi hồ sơ Đang xử lý.")
                    return redirect("admin:social_messages_intakesubmission_change", object_id)

                reason = request.POST.get("return_reason")
                if reason:
                    obj.processing_status = "returned"
                    obj.save(update_fields=["processing_status"])
                    assignment.status = "returned"
                    assignment.return_reason = reason
                    assignment.save(update_fields=["status", "return_reason"])
                    
                    IntakeSubmissionHistory.objects.create(
                        submission=obj,
                        user=request.user,
                        action='return',
                        note=reason
                    )
                    messages.success(request, "Đã trả lại hồ sơ.")
                    return redirect("admin:social_messages_intakesubmission_change", object_id)
            elif action_name == "complete":
                if assignment.role == "co_handler" and obj.processing_status != "in_progress":
                    messages.error(request, "Người phối hợp chỉ được thao tác khi hồ sơ Đang xử lý.")
                    return redirect("admin:social_messages_intakesubmission_change", object_id)

                if assignment.role == "main":
                    pending_co_handlers = obj.assignments.filter(role="co_handler").exclude(status="completed")
                    if pending_co_handlers.exists():
                        messages.error(request, "Không thể hoàn thành xử lý. Yêu cầu tất cả người phối hợp phải hoàn thành trước.")
                        return redirect("admin:social_messages_intakesubmission_change", object_id)

                note = request.POST.get("processing_note")
                if note:
                    assignment.status = "completed"
                    assignment.processing_note = note
                    assignment.save(update_fields=["status", "processing_note"])

                    IntakeSubmissionHistory.objects.create(
                        submission=obj,
                        user=request.user,
                        action='complete',
                        note=note
                    )

                    if assignment.role == "main":
                        obj.processing_status = "completed"
                        obj.save(update_fields=["processing_status"])
                    else:
                        all_completed = not obj.assignments.exclude(status="completed").exists()
                        if all_completed:
                            obj.processing_status = "completed"
                            obj.save(update_fields=["processing_status"])
                    messages.success(request, "Đã hoàn thành xử lý.")
                    return redirect("admin:social_messages_intakesubmission_change", object_id)

        context = self.admin_site.each_context(request)
        context.update({
            "original": obj,
            "action_name": action_name,
        })
        return render(request, "admin/social_messages/intakesubmission/action_form.html", context)

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

    @admin.display(description="Trạng thái hệ thống")
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

    @admin.display(description="Trạng thái xử lý")
    def processing_status_badge(self, obj):
        color_map = {
            "unassigned": "secondary",
            "pending": "warning",
            "in_progress": "info",
            "completed": "success",
            "returned": "danger",
        }
        label = obj.get_processing_status_display() if hasattr(obj, "get_processing_status_display") else obj.processing_status
        return badge(label, color_map.get(obj.processing_status, "secondary"))


from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Hồ sơ người dùng'

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, UserAdmin)

