from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from .models import Message, Conversation, IntakeSubmission, Report


@staff_member_required
def admin_dashboard(request):
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_7_days = today_start - timedelta(days=6)

    messages_today = Message.objects.filter(created_at__gte=today_start).count()

    zalo_messages_today = Message.objects.filter(
        created_at__gte=today_start,
        conversation__channel__platform="zalo",
    ).count()

    facebook_messages_today = Message.objects.filter(
        created_at__gte=today_start,
        conversation__channel__platform="facebook",
    ).count()

    open_conversations = Conversation.objects.filter(status="open").count()

    submissions_today = IntakeSubmission.objects.filter(
        created_at__gte=today_start
    ).count()

    pending_submissions = IntakeSubmission.objects.exclude(
        status="responded"
    ).count()

    high_priority_submissions = IntakeSubmission.objects.filter(
        priority__in=["high", "urgent", "critical"]
    ).count()

    reports_completed_today = Report.objects.filter(
        created_at__gte=today_start,
        status="completed",
    ).count()

    message_chart_raw = (
        Message.objects
        .filter(created_at__date__gte=last_7_days.date())
        .extra(select={"day": "date(created_at)"})
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    status_chart_raw = (
        IntakeSubmission.objects
        .values("status")
        .annotate(total=Count("id"))
        .order_by("status")
    )

    context = {
        "title": "Dashboard tổng quan",
        "messages_today": messages_today,
        "zalo_messages_today": zalo_messages_today,
        "facebook_messages_today": facebook_messages_today,
        "open_conversations": open_conversations,
        "submissions_today": submissions_today,
        "pending_submissions": pending_submissions,
        "high_priority_submissions": high_priority_submissions,
        "reports_completed_today": reports_completed_today,
        "message_chart": list(message_chart_raw),
        "status_chart": list(status_chart_raw),
    }

    return render(request, "admin/custom_dashboard.html", context)