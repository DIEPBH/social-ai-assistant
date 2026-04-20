from celery import shared_task
from django.utils import timezone

from social_messages.services.ai_service import AIAnalysisService
from social_messages.models import Message, MessageAnalysis, Report
from social_messages.services.report_exporter import DailyReportExporter
from social_messages.services.command_parser import CommandParser
from social_messages.services.admin_guard import AdminGuard
from django.conf import settings
from social_messages.services.zalo_sender import ZaloOASender

@shared_task
def debug_task(message="hello from celery"):
    return {
        "status": "success",
        "message": message,
        "executed_at": timezone.now().isoformat(),
    }


@shared_task
def process_message_analysis(message_id: int):
    try:
        message = Message.objects.select_related("conversation", "conversation__channel").get(id=message_id)

        analysis, _ = MessageAnalysis.objects.get_or_create(
            message=message,
            defaults={"status": "pending"},
        )

        ai_service = AIAnalysisService()
        ai_result = ai_service.analyze_message(message.content or "")

        analysis.status = "processed"
        analysis.topic = ai_result.get("topic")
        analysis.sentiment = ai_result.get("sentiment")
        analysis.priority = ai_result.get("priority")
        analysis.summary = ai_result.get("summary")
        analysis.result_payload = {
            "message_id": message.id,
            "platform": message.conversation.channel.platform,
            "channel": message.conversation.channel.name,
            "content": message.content,
            "topic": ai_result.get("topic"),
            "sentiment": ai_result.get("sentiment"),
            "priority": ai_result.get("priority"),
            "engine": ai_result.get("engine"),
            "selected_engine": ai_result.get("selected_engine"),
            "raw_result": ai_result.get("raw_result", {}),
        }
        analysis.error_message = ""
        analysis.processed_at = timezone.now()
        analysis.save()

        return {
            "status": "success",
            "message_id": message.id,
            "analysis_id": analysis.id,
            "topic": ai_result.get("topic"),
            "sentiment": ai_result.get("sentiment"),
            "priority": ai_result.get("priority"),
            "engine": ai_result.get("engine"),
            "selected_engine": ai_result.get("selected_engine"),
        }

    except Message.DoesNotExist:
        return {
            "status": "error",
            "error": f"Message with id {message_id} does not exist",
        }

    except Exception as exc:
        analysis = MessageAnalysis.objects.filter(message_id=message_id).first()
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(exc)
            analysis.processed_at = timezone.now()
            analysis.save()

        return {
            "status": "error",
            "message_id": message_id,
            "error": str(exc),
        }

@shared_task
def generate_daily_report(report_id: int, admin_message_id: int = None):
    try:
        report = Report.objects.get(id=report_id)
        report.status = "processing"
        report.save(update_fields=["status"])

        exporter = DailyReportExporter(report)
        file_path = exporter.export()

        report.status = "completed"
        report.file_path = file_path
        report.file_name = file_path.split("/")[-1]
        report.completed_at = timezone.now()
        report.note = "Báo cáo được tạo thành công"
        report.save()

        if admin_message_id:
            send_report_result_to_zalo.delay(report.id, admin_message_id)

        return {
            "status": "success",
            "report_id": report.id,
            "file_path": file_path,
            "file_name": report.file_name,
        }

    except Report.DoesNotExist:
        return {
            "status": "error",
            "error": f"Report with id {report_id} does not exist",
        }

    except Exception as exc:
        report = Report.objects.filter(id=report_id).first()
        if report:
            report.status = "failed"
            report.note = str(exc)
            report.completed_at = timezone.now()
            report.save()

        return {
            "status": "error",
            "report_id": report_id,
            "error": str(exc),
        }

@shared_task
def process_admin_command(message_id: int):
    try:
        message = Message.objects.select_related("conversation", "conversation__channel").get(id=message_id)
        
        if message.conversation.channel.platform != "zalo":
            return {
                "status": "ignored",
                "message_id": message.id,
                "reason": "not_zalo_platform",
            }

        guard = AdminGuard()
        if not guard.is_zalo_admin(message.sender_id):
            return {
                "status": "ignored",
                "message_id": message.id,
                "reason": "sender_not_allowed",
            }

        parser = CommandParser()
        parsed = parser.parse(message.content or "")

        if not parsed.get("is_command"):
            return {
                "status": "ignored",
                "message_id": message.id,
                "reason": "not_a_command",
            }

        if parsed["command_type"] == "generate_daily_report":
            report = Report.objects.create(
                report_type=parsed["report_type"],
                title=parsed["title"],
                from_time=parsed["from_time"],
                to_time=parsed["to_time"],
                status="pending",
                note=f"Tạo từ lệnh quản trị. Message ID: {message.id}",
            )

            report_task = generate_daily_report.delay(report.id, message.id)

            #send_back_task = send_report_result_to_zalo.delay(report.id, message.id)

            return {
                "status": "success",
                "message_id": message.id,
                "command_type": parsed["command_type"],
                "report_id": report.id,
                "report_task_id": report_task.id,
                "send_back_task_id": send_back_task.id,
            }

        return {
            "status": "ignored",
            "message_id": message.id,
            "reason": "unsupported_command",
        }

    except Message.DoesNotExist:
        return {
            "status": "error",
            "error": f"Message with id {message_id} does not exist",
        }

    except Exception as exc:
        return {
            "status": "error",
            "message_id": message_id,
            "error": str(exc),
        }

@shared_task
def send_report_result_to_zalo(report_id: int, admin_message_id: int):
    try:
        report = Report.objects.get(id=report_id)
        admin_message = Message.objects.select_related(
            "conversation",
            "conversation__channel",
        ).get(id=admin_message_id)

        channel = admin_message.conversation.channel
        access_token = channel.access_token
        user_id = admin_message.sender_id

        if not settings.PUBLIC_BASE_URL:
            raise ValueError("Missing PUBLIC_BASE_URL in settings")

        if not report.file_name:
            raise ValueError("Report file_name is empty")

        download_url = f"{settings.PUBLIC_BASE_URL}/media/reports/{report.file_name}"

        text = (
            f"Đã tạo xong báo cáo: {report.title}\n"
            f"Từ: {report.from_time.strftime('%d-%m-%Y %H:%M:%S')}\n"
            f"Đến: {report.to_time.strftime('%d-%m-%Y %H:%M:%S')}\n"
            f"Tải file: {download_url}"
        )

        sender = ZaloOASender()
        zalo_result = sender.send_text_message(
            access_token=access_token,
            user_id=user_id,
            text=text,
        )

        report.note = (report.note or "") + f"\nĐã gửi kết quả về Zalo cho user {user_id}"
        report.save(update_fields=["note"])

        return {
            "status": "success",
            "report_id": report.id,
            "admin_message_id": admin_message.id,
            "zalo_result": zalo_result,
        }

    except Exception as exc:
        return {
            "status": "error",
            "report_id": report_id,
            "admin_message_id": admin_message_id,
            "error": str(exc),
        }