import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from pathlib import Path
from social_messages.models import IntakeSubmission, Message, MessageAnalysis, Report
from social_messages.services.admin_guard import AdminGuard
from social_messages.services.ai_service import AIAnalysisService
from social_messages.services.command_parser import CommandParser
from social_messages.services.report_exporter import DailyReportExporter
from social_messages.services.zalo_sender import ZaloOASender
from social_messages.services.keyword_engine import KeywordEngine
from social_messages.services.zalo_token_refresher import ZaloTokenRefresher
from social_messages.models import Channel
logger = logging.getLogger(__name__)


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
        message = Message.objects.select_related(
            "conversation",
            "conversation__channel",
        ).get(id=message_id)

        analysis, _ = MessageAnalysis.objects.get_or_create(
            message=message,
            defaults={"status": "pending"},
        )

        ai_service = AIAnalysisService()
        ai_result = ai_service.analyze_message(message.content or "")

        analysis.status = "processed"
        analysis.topic = ai_result.get("topic", "khác")
        analysis.sentiment = ai_result.get("sentiment", "trung lập")
        analysis.priority = ai_result.get("priority", "normal")
        analysis.summary = ai_result.get("summary") or f"Nội dung người dân gửi: {message.content or ''}"
        analysis.result_payload = {
            "message_id": message.id,
            "platform": message.conversation.channel.platform,
            "channel": message.conversation.channel.name,
            "content": message.content,
            "topic": ai_result.get("topic"),
            "sentiment": ai_result.get("sentiment"),
            "priority": ai_result.get("priority"),
            "summary": ai_result.get("summary"),
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
            "topic": analysis.topic,
            "sentiment": analysis.sentiment,
            "priority": analysis.priority,
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

        logger.exception("process_message_analysis failed for message_id=%s", message_id)

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
        logger.info("GENERATING REPORT report_id=%s", report.id)
        exporter = DailyReportExporter(report)  
        file_path = exporter.export()

        if not file_path or not Path(file_path).exists():
            raise ValueError("Exporter did not create report file")

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

        logger.exception("generate_daily_report failed for report_id=%s", report_id)

        return {
            "status": "error",
            "report_id": report_id,
            "error": str(exc),
        }


@shared_task
def process_admin_command(message_id: int):
    try:
        message = Message.objects.select_related(
            "conversation",
            "conversation__channel",
        ).get(id=message_id)
        logger.info("test process_admin_command message_id=%s platform=%s sender_id=%s content=%s",
            message.id,
            message.conversation.channel.platform,
            message.sender_id,
            message.content,
        )
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
        if parsed.get("command_type") == "invalid_report_date":
            return {
                "status": "error",
                "message_id": message.id,
                "reason": "invalid_report_date",
                "error": parsed.get("error", "Ngày báo cáo không hợp lệ"),
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

            return {
                "status": "success",
                "message_id": message.id,
                "command_type": parsed["command_type"],
                "report_id": report.id,
                "report_task_id": report_task.id,
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
        logger.exception("process_admin_command failed for message_id=%s", message_id)
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
        logger.exception(
            "send_report_result_to_zalo failed report_id=%s admin_message_id=%s",
            report_id,
            admin_message_id,
        )
        return {
            "status": "error",
            "report_id": report_id,
            "admin_message_id": admin_message_id,
            "error": str(exc),
        }


@shared_task
def process_intake_submission(submission_id: int):
    try:
        submission = IntakeSubmission.objects.select_related(
            "conversation",
            "conversation__channel",
        ).get(id=submission_id)
    except IntakeSubmission.DoesNotExist:
        return {
            "status": "error",
            "reason": "submission_not_found",
            "submission_id": submission_id,
        }

    try:
        keyword_engine = KeywordEngine()
        keyword_result = keyword_engine.analyze_submission(submission)

        ai_result = None
        analysis_result = keyword_result

        if not analysis_result:
            ai_service = AIAnalysisService()
            ai_input = {
                "intent": submission.intent,
                "citizen_name": submission.citizen_name,
                "phone_number": submission.phone_number,
                "address": submission.address,
                "content": submission.content,
                "event_time": submission.event_time,
                "event_location": submission.event_location,
                "related_person": submission.related_person,
                "urgency_level": submission.urgency_level,
            }
            ai_result = ai_service.analyze_message(ai_input)
            analysis_result = ai_result

        if submission.intent == "complaint":
            result_payload = build_complaint_result(submission)
            reply_text = (
                "Hệ thống đã tiếp nhận nội dung khiếu nại của anh/chị. "
                "Thông tin đã được chuyển đến bộ phận tiếp nhận để rà soát."
            )

        elif submission.intent == "crime_report":
            result_payload = build_crime_report_result(submission)
            if result_payload.get("urgency") == "urgent" or result_payload.get("immediate_risk"):
                reply_text = (
                    "Hệ thống đã tiếp nhận tin báo. "
                    "Nếu tình huống đang khẩn cấp hoặc đe dọa trực tiếp đến an toàn, "
                    "vui lòng liên hệ ngay cơ quan công an hoặc số khẩn cấp tại địa phương."
                )
            else:
                reply_text = (
                    "Hệ thống đã tiếp nhận tin báo của anh/chị "
                    "và sẽ chuyển xử lý theo quy trình."
                )

        elif submission.intent == "admin_procedure":
            result_payload = build_admin_procedure_result(submission)
            reply_text = result_payload.get(
                "draft_reply",
                "Hệ thống đã tiếp nhận câu hỏi về thủ tục hành chính của anh/chị."
            )

        else:
            submission.status = "rejected"
            submission.raw_extracted_data = {
                **submission.raw_extracted_data,
                "processing_error": {
                    "reason": "unknown_intent",
                    "processed_at": timezone.now().isoformat(),
                },
            }
            submission.save(update_fields=["status", "raw_extracted_data"])
            return {
                "status": "error",
                "reason": "unknown_intent",
                "submission_id": submission.id,
            }

        from social_messages.services.outbound_message_service import OutboundMessageService
        outbound_service = OutboundMessageService()
        outbound_result = outbound_service.send_text(submission.conversation, reply_text)

        submission.topic = analysis_result.get("topic", "")
        submission.sentiment = analysis_result.get("sentiment", "")
        submission.priority = analysis_result.get("priority", "")
        submission.summary = analysis_result.get("summary", "")
        submission.response_text = reply_text
        submission.raw_extracted_data = {
            **submission.raw_extracted_data,
            "analysis_result": analysis_result,
            "analysis_source": "keyword" if keyword_result else "ai",
            "processing_result": result_payload,
            "outbound_result": outbound_result,
        }
        submission.status = "responded"
        submission.save(update_fields=[
            "topic",
            "sentiment",
            "priority",
            "summary",
            "response_text",
            "raw_extracted_data",
            "status",
        ])

        return {
            "status": "success",
            "submission_id": submission.id,
            "intent": submission.intent,
            "topic": submission.topic,
            "priority": submission.priority,
            "analysis_source": "keyword" if keyword_result else "ai",
            "processing_result": result_payload,
            "outbound_result": outbound_result,
        }

    except Exception as exc:
        submission.status = "rejected"
        submission.raw_extracted_data = {
            **submission.raw_extracted_data,
            "processing_error": {
                "reason": str(exc),
                "processed_at": timezone.now().isoformat(),
            },
        }
        submission.save(update_fields=["status", "raw_extracted_data"])

        logger.exception("process_intake_submission failed for submission_id=%s", submission_id)

        return {
            "status": "error",
            "submission_id": submission.id,
            "error": str(exc),
        }


def build_complaint_result(submission: IntakeSubmission) -> dict:
    priority = "normal"

    content_lower = (submission.content or "").lower()
    if any(keyword in content_lower for keyword in ["khẩn cấp", "nghiêm trọng", "gấp", "ngay lập tức"]):
        priority = "high"

    return {
        "intent": "complaint",
        "summary": submission.content,
        "priority": priority,
        "suggested_department": "bo_phan_tiep_nhan_khieu_nai",
        "requires_human_review": True,
        "processed_at": timezone.now().isoformat(),
    }


def build_crime_report_result(submission: IntakeSubmission) -> dict:
    urgency = "normal"
    immediate_risk = False

    content_lower = (submission.content or "").lower()
    if any(keyword in content_lower for keyword in [
        "vũ khí", "đe dọa", "đánh nhau", "cháy", "nổ", "bắt cóc", "khẩn cấp"
    ]):
        urgency = "urgent"
        immediate_risk = True

    if submission.urgency_level:
        urgency = submission.urgency_level

    return {
        "intent": "crime_report",
        "summary": submission.content,
        "urgency": urgency,
        "immediate_risk": immediate_risk,
        "suggested_department": "co_quan_cong_an",
        "requires_human_review": True,
        "processed_at": timezone.now().isoformat(),
    }


def build_admin_procedure_result(submission: IntakeSubmission) -> dict:
    content_lower = (submission.content or "").lower()

    suggested_procedure_group = "thu_tuc_hanh_chinh_chung"
    if "hộ khẩu" in content_lower or "cư trú" in content_lower:
        suggested_procedure_group = "cu_tru_ho_khau"
    elif "khai sinh" in content_lower:
        suggested_procedure_group = "ho_tich_khai_sinh"
    elif "đăng ký kinh doanh" in content_lower:
        suggested_procedure_group = "dang_ky_kinh_doanh"

    draft_reply = (
        "Hệ thống đã ghi nhận câu hỏi về thủ tục hành chính của anh/chị. "
        "Cán bộ phụ trách sẽ rà soát và phản hồi theo nhóm thủ tục phù hợp."
    )

    return {
        "intent": "admin_procedure",
        "summary": submission.content,
        "suggested_procedure_group": suggested_procedure_group,
        "draft_reply": draft_reply,
        "requires_human_review": True,
        "processed_at": timezone.now().isoformat(),
    }

@shared_task
def refresh_zalo_channel_token(channel_id: int):
    try:
        channel = Channel.objects.get(id=channel_id)
    except Channel.DoesNotExist:
        return {
            "status": "error",
            "reason": "channel_not_found",
            "channel_id": channel_id,
        }

    refresher = ZaloTokenRefresher()
    return refresher.refresh_channel_token(channel)


@shared_task
def refresh_all_zalo_tokens_if_needed():
    refresher = ZaloTokenRefresher()

    results = []
    channels = Channel.objects.filter(
        platform="zalo",
        is_active=True,
    )

    for channel in channels:
        results.append(refresher.refresh_if_needed(channel))

    return {
        "status": "success",
        "total": len(results),
        "results": results,
    }