import logging
import os

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from pathlib import Path
from social_messages.models import IntakeSubmission, Message, MessageAnalysis, Report, UserProfile
from social_messages.services.admin_guard import AdminGuard
from social_messages.services.ai_service import AIAnalysisService
from social_messages.services.command_parser import CommandParser
from social_messages.services.report_exporter import DailyReportExporter
from social_messages.services.zalo_sender import ZaloOASender
from social_messages.services.keyword_engine import KeywordEngine
from social_messages.services.zalo_token_refresher import ZaloTokenRefresher
from social_messages.models import Channel
from social_messages.services.admin_insight_service import AdminInsightService
from social_messages.services.admin_reply_service import AdminReplyService
from datetime import datetime, time, timedelta
from social_messages.services.admin_ai_interpreter import AdminAIInterpreter
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
        
        requester_user = None
        is_admin = False
        is_specialist = False
        
        if admin_message_id:
            try:
                admin_msg = Message.objects.get(id=admin_message_id)
                profile = UserProfile.objects.filter(zalo_id=admin_msg.sender_id, user__is_active=True).first()
                if profile and profile.user:
                    requester_user = profile.user
                    groups = list(requester_user.groups.values_list("name", flat=True))
                    lower_groups = [g.lower() for g in groups]
                    if any("quản trị viên" in g for g in lower_groups):
                        is_admin = True
                    elif any("chuyên viên" in g for g in lower_groups):
                        is_specialist = True
            except Message.DoesNotExist:
                pass
                
        exporter = DailyReportExporter(
            report, 
            requester_user=requester_user, 
            is_admin=is_admin, 
            is_specialist=is_specialist
        )  
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
        logger.info(
            "test process_admin_command message_id=%s platform=%s sender_id=%s content=%s",
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

        user = guard.get_user_by_zalo_id(message.sender_id)
        if not user:
            return {
                "status": "ignored",
                "message_id": message.id,
                "reason": "user_not_found_or_inactive",
            }

        parser = CommandParser()
        parsed = parser.parse(message.content or "")

        # Fallback AI chỉ dùng cho các nhóm lệnh hệ thống cũ. Lệnh do admin khai báo
        # trong DB sẽ được CommandParser xử lý trước qua AdminCommand/AdminCommandPattern.
        if not parsed.get("is_command"):
            ai_parsed = AdminAIInterpreter().interpret(message.content or "")

            if ai_parsed.get("is_command"):
                if ai_parsed.get("command_type") in ["generate_daily_report", "generate_custom_report"]:
                    parsed = build_report_command_from_ai(ai_parsed)
                else:
                    parsed = ai_parsed
            else:
                parsed = ai_parsed

        if not parsed.get("is_command"):
            reply_text = parser.get_help_text()
            outbound_result = AdminReplyService().send(message, reply_text)

            return {
                "status": "ignored",
                "message_id": message.id,
                "reason": "not_a_supported_admin_command",
                "outbound_result": outbound_result,
            }

        if parsed.get("command_type") == "invalid_report_date":
            reply_text = parsed.get("error", "Ngày báo cáo không hợp lệ")
            outbound_result = AdminReplyService().send(message, reply_text)
            return {
                "status": "error",
                "message_id": message.id,
                "reason": "invalid_report_date",
                "error": reply_text,
                "outbound_result": outbound_result,
            }

        if parsed["command_type"] == "static_reply":
            reply_text = parsed.get("reply_text") or "Đã nhận lệnh quản trị."
            outbound_result = AdminReplyService().send(message, reply_text)
            return {
                "status": "success",
                "message_id": message.id,
                "command_type": "static_reply",
                "admin_command_id": parsed.get("admin_command_id"),
                "outbound_result": outbound_result,
            }

        if parsed["command_type"] == "today_insight":
            reply_text = AdminInsightService().get_today_insight_text()
            outbound_result = AdminReplyService().send(message, reply_text)

            return {
                "status": "success",
                "message_id": message.id,
                "command_type": "today_insight",
                "admin_command_id": parsed.get("admin_command_id"),
                "outbound_result": outbound_result,
            }

        if parsed["command_type"] == "system_status":
            reply_text = AdminInsightService().get_system_status_text()
            outbound_result = AdminReplyService().send(message, reply_text)

            return {
                "status": "success",
                "message_id": message.id,
                "command_type": "system_status",
                "admin_command_id": parsed.get("admin_command_id"),
                "outbound_result": outbound_result,
            }

        if parsed["command_type"] == "generate_daily_report":
            report = Report.objects.create(
                report_type=parsed["report_type"],
                title=parsed["title"],
                from_time=parsed["from_time"],
                to_time=parsed["to_time"],
                status="pending",
                note=(
                    f"Tạo từ lệnh quản trị. Message ID: {message.id}. "
                    f"AdminCommand ID: {parsed.get('admin_command_id', '')}"
                ),
            )

            report_task = generate_daily_report.delay(report.id, message.id)
            AdminReplyService().send(
                message,
                f"Đã nhận lệnh tạo báo cáo: {report.title}\n"
                "Hệ thống đang xử lý. Khi tạo xong file, tôi sẽ gửi link tải về Zalo."
            )
            return {
                "status": "success",
                "message_id": message.id,
                "command_type": parsed["command_type"],
                "admin_command_id": parsed.get("admin_command_id"),
                "report_id": report.id,
                "report_task_id": report_task.id,
            }

        if parsed["command_type"] == "list_submissions":
            from social_messages.services.admin_submission_service import AdminSubmissionService
            filter_type = parsed.get("filter_type", "default")
            target_date = parsed.get("target_date")
            reply_text = AdminSubmissionService().format_submissions_list(
                user=user,
                filter_type=filter_type,
                target_date=target_date,
            )
            outbound_result = AdminReplyService().send(message, reply_text)
            return {
                "status": "success",
                "message_id": message.id,
                "command_type": "list_submissions",
                "filter_type": filter_type,
                "admin_command_id": parsed.get("admin_command_id"),
                "outbound_result": outbound_result,
            }

        if parsed["command_type"] == "submission_detail":
            sub_id = parsed.get("submission_id")
            if not sub_id:
                reply_text = "Vui lòng nhập mã hồ sơ hợp lệ. Ví dụ: 'xem hồ sơ 114'"
                outbound_result = AdminReplyService().send(message, reply_text)
                return {
                    "status": "error",
                    "message_id": message.id,
                    "command_type": "submission_detail",
                    "error": "missing_submission_id",
                    "outbound_result": outbound_result,
                }

            from social_messages.services.admin_submission_service import AdminSubmissionService
            submission_service = AdminSubmissionService()
            has_access, reply_text, submission = submission_service.get_submission_detail(user, sub_id)

            outbound_result = AdminReplyService().send(message, reply_text)

            attachments_sent = 0
            if has_access and submission:
                attachments = submission_service.collect_submission_attachments(submission)
                if attachments:
                    import time
                    from social_messages.services.zalo_sender import ZaloOASender
                    channel = message.conversation.channel
                    sender = ZaloOASender()
                    access_token = channel.access_token
                    target_user_id = message.sender_id

                    max_send = 8
                    for idx, att in enumerate(attachments[:max_send]):
                        caption = f"📎 Tài liệu #{idx + 1} của hồ sơ #{submission.id}"
                        try:
                            res = sender.send_attachment(
                                access_token=access_token,
                                user_id=target_user_id,
                                attachment=att,
                                caption=caption,
                            )
                            if res.get("status") == "success":
                                attachments_sent += 1
                            time.sleep(0.5)
                        except Exception as e:
                            logger.warning("Failed to send attachment %s to admin: %s", att.get("url"), e)

                    if len(attachments) > max_send:
                        remaining = len(attachments) - max_send
                        AdminReplyService().send(
                            message,
                            f"ℹ️ Hồ sơ còn {remaining} tài liệu đính kèm khác. Anh/chị có thể đăng nhập trang web quản trị để xem toàn bộ."
                        )

            return {
                "status": "success",
                "message_id": message.id,
                "command_type": "submission_detail",
                "submission_id": sub_id,
                "has_access": has_access,
                "attachments_sent": attachments_sent,
                "admin_command_id": parsed.get("admin_command_id"),
                "outbound_result": outbound_result,
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

        if not report.file_name or not report.file_path:
            raise ValueError("Report file is missing")

        text = (
            f"Đã tạo xong báo cáo: {report.title}\n"
            f"Từ: {report.from_time.strftime('%d-%m-%Y %H:%M:%S')}\n"
            f"Đến: {report.to_time.strftime('%d-%m-%Y %H:%M:%S')}"
        )

        sender = ZaloOASender()
        zalo_result_text = sender.send_text_message(
            access_token=access_token,
            user_id=user_id,
            text=text,
        )

        try:
            file_token = sender.upload_file(access_token, report.file_path)
            zalo_result_file = sender.send_file_message(
                access_token=access_token,
                user_id=user_id,
                file_token=file_token
            )
            zalo_result = {"text": zalo_result_text, "file": zalo_result_file}
        except Exception as e:
            logger.error("Failed to send file directly to Zalo: %s", e)
            if settings.PUBLIC_BASE_URL:
                relative_path = Path(report.file_path).relative_to(settings.MEDIA_ROOT)
                download_url = f"{settings.PUBLIC_BASE_URL}/media/{relative_path.as_posix()}"
                fallback_text = f"Không thể gửi file trực tiếp. Tải file: {download_url}"
                sender.send_text_message(access_token, user_id, fallback_text)
            zalo_result = {"text": zalo_result_text, "error": str(e)}

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
            "category",
        ).get(id=submission_id)
    except IntakeSubmission.DoesNotExist:
        return {
            "status": "error",
            "reason": "submission_not_found",
            "submission_id": submission_id,
        }

    try:
        category = submission.category

        keyword_engine = KeywordEngine()
        keyword_result = keyword_engine.analyze_submission(submission)

        analysis_result = keyword_result
        if not analysis_result:
            ai_service = AIAnalysisService()
            ai_input = {
                "category": {
                    "id": category.id if category else None,
                    "code": category.code if category else submission.intent,
                    "name": category.name if category else submission.intent,
                    "description": category.description if category else "",
                },
                "citizen_name": submission.citizen_name,
                "phone_number": submission.phone_number,
                "address": submission.address,
                "content": submission.content,
                "event_time": submission.event_time,
                "event_location": submission.event_location,
                "related_person": submission.related_person,
                "urgency_level": submission.urgency_level,
                "raw_extracted_data": submission.raw_extracted_data,
            }
            analysis_result = ai_service.analyze_message(ai_input)

        result_payload = build_dynamic_intake_result(submission, analysis_result)
        reply_text = build_dynamic_reply_text(submission, analysis_result, result_payload)

        from social_messages.services.outbound_message_service import OutboundMessageService
        outbound_service = OutboundMessageService()
        outbound_result = outbound_service.send_text(submission.conversation, reply_text)

        submission.topic = analysis_result.get("topic", "") or (category.default_topic if category else "")
        submission.sentiment = analysis_result.get("sentiment", "") or (category.default_sentiment if category else "")
        submission.priority = analysis_result.get("priority", "") or (category.default_priority if category else "normal")
        submission.summary = analysis_result.get("summary", "") or submission.content
        submission.response_text = reply_text
        submission.raw_extracted_data = {
            **(submission.raw_extracted_data or {}),
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
            "category": category.code if category else submission.intent,
            "topic": submission.topic,
            "priority": submission.priority,
            "analysis_source": "keyword" if keyword_result else "ai",
            "processing_result": result_payload,
            "outbound_result": outbound_result,
        }

    except Exception as exc:
        submission.status = "rejected"
        submission.raw_extracted_data = {
            **(submission.raw_extracted_data or {}),
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


def build_dynamic_intake_result(submission: IntakeSubmission, analysis_result: dict) -> dict:
    category = submission.category
    priority = analysis_result.get("priority") or (category.default_priority if category else "normal")

    return {
        "category_id": category.id if category else None,
        "category_code": category.code if category else submission.intent,
        "category_name": category.name if category else submission.intent,
        "summary": analysis_result.get("summary") or submission.content,
        "priority": priority,
        "suggested_department": category.default_department if category else "",
        "requires_human_review": category.requires_human_review if category else True,
        "processed_at": timezone.now().isoformat(),
    }


def build_dynamic_reply_text(submission: IntakeSubmission, analysis_result: dict, result_payload: dict) -> str:
    category = submission.category

    if analysis_result.get("response_text"):
        return analysis_result["response_text"]

    priority = result_payload.get("priority") or "normal"
    if category and priority in {"high", "urgent", "critical"} and category.urgent_reply_text:
        return category.urgent_reply_text

    if category and category.success_reply_text:
        return category.success_reply_text

    category_name = category.name if category else "nội dung"
    return (
        f"Hệ thống đã tiếp nhận {category_name.lower()} của anh/chị. "
        "Thông tin đã được chuyển đến bộ phận phụ trách để rà soát và xử lý theo quy trình."
    )


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
def fetch_zalo_user_profile(conversation_id: int):
    from social_messages.models import Conversation
    from social_messages.services.zalo_sender import ZaloOASender
    
    try:
        conversation = Conversation.objects.select_related("channel").get(id=conversation_id)
        if conversation.channel.platform != "zalo" or conversation.customer_name:
            return {"status": "ignored"}
            
        access_token = conversation.channel.access_token or getattr(settings, "ZALO_OA_ACCESS_TOKEN", "")
        if not access_token:
            return {"status": "error", "reason": "no_access_token"}
            
        sender = ZaloOASender()
        profile_data = sender.get_user_profile(access_token, conversation.customer_id)
        
        if profile_data.get("error") == 0 and "data" in profile_data:
            display_name = profile_data["data"].get("display_name")
            if display_name:
                conversation.customer_name = display_name
                conversation.save(update_fields=["customer_name", "updated_at"])
                return {"status": "success", "display_name": display_name}
                
        return {"status": "failed", "response": profile_data}
    except Exception as e:
        logger.exception("fetch_zalo_user_profile failed")
        return {"status": "error", "error": str(e)}

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

def build_report_command_from_ai(parsed: dict):
    now = timezone.localtime()

    if parsed.get("command_type") == "generate_daily_report":
        date_type = parsed.get("date_type")

        if date_type == "today":
            target_date = now.date()
        elif date_type == "yesterday":
            target_date = now.date() - timedelta(days=1)
        elif date_type == "specific":
            try:
                target_date = datetime.strptime(parsed.get("date"), "%Y-%m-%d").date()
            except Exception:
                return {
                    "is_command": True,
                    "command_type": "invalid_report_date",
                    "error": "AI nhận diện ngày báo cáo không hợp lệ",
                }
        else:
            return {
                "is_command": False,
                "command_type": None,
                "reason": "missing_report_date",
            }

        return {
            "is_command": True,
            "command_type": "generate_daily_report",
            "title": f"Báo cáo ngày {target_date.strftime('%d-%m-%Y')}",
            "from_time": start_of_day(target_date),
            "to_time": end_of_day(target_date),
            "report_type": "daily",
            "source": "ai",
        }

    if parsed.get("command_type") == "generate_custom_report":
        range_value = parsed.get("range")

        if range_value == "this_week":
            start_date = now.date() - timedelta(days=now.weekday())
            end_date = start_date + timedelta(days=6)

            return {
                "is_command": True,
                "command_type": "generate_daily_report",
                "title": f"Báo cáo tuần {start_date.strftime('%d-%m-%Y')} đến {end_date.strftime('%d-%m-%Y')}",
                "from_time": start_of_day(start_date),
                "to_time": end_of_day(end_date),
                "report_type": "custom",
                "source": "ai",
            }

        if range_value == "this_month":
            start_date = now.date().replace(day=1)

            if now.month == 12:
                next_month = now.date().replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.date().replace(month=now.month + 1, day=1)

            end_date = next_month - timedelta(days=1)

            return {
                "is_command": True,
                "command_type": "generate_daily_report",
                "title": f"Báo cáo tháng {now.strftime('%m-%Y')}",
                "from_time": start_of_day(start_date),
                "to_time": end_of_day(end_date),
                "report_type": "custom",
                "source": "ai",
            }

    return parsed


def start_of_day(target_date):
    return timezone.make_aware(datetime.combine(target_date, time.min))


def end_of_day(target_date):
    return timezone.make_aware(datetime.combine(target_date, time.max))

@shared_task
def cleanup_integration_logs():
    from social_messages.models import IntegrationLog
    retention_days = int(os.getenv("LOG_RETENTION_DAYS", 7))
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    
    deleted_count, _ = IntegrationLog.objects.filter(created_at__lt=cutoff_date).delete()
    logger.info("Cleaned up %s old IntegrationLogs older than %s days", deleted_count, retention_days)
    return {
        "status": "success",
        "deleted_count": deleted_count,
    }


@shared_task
def send_daily_24h_summary_report():
    from social_messages.models import IntakeSubmission, Channel, UserProfile, IntakeSubmissionAssignment
    from social_messages.services.zalo_sender import ZaloOASender
    from django.conf import settings
    from django.utils import timezone
    from datetime import timedelta
    
    end_time = timezone.now()
    start_time = end_time - timedelta(days=1)
    
    qs = IntakeSubmission.objects.filter(created_at__gte=start_time, created_at__lt=end_time)
    
    total = qs.count()
    zalo_count = qs.filter(conversation__channel__platform='zalo').count()
    fb_count = qs.filter(conversation__channel__platform='facebook').count()
    
    high_count = qs.filter(priority__iexact='high').count()
    med_count = qs.filter(priority__iexact='medium').count()
    low_count = qs.filter(priority__iexact='low').count()
    unknown_count = total - (high_count + med_count + low_count)
    
    # 24h Processing status for Admin
    unassigned_today = qs.filter(processing_status='unassigned').count()
    pending_today = qs.filter(processing_status='pending').count()
    in_progress_today = qs.filter(processing_status='in_progress').count()
    completed_today = qs.filter(processing_status='completed').count()
    returned_today = qs.filter(processing_status='returned').count()
    
    total_unassigned = IntakeSubmission.objects.filter(processing_status='unassigned').count()
    
    # Get timezone from settings to format correctly
    from zoneinfo import ZoneInfo
    local_tz = ZoneInfo(getattr(settings, 'TIME_ZONE', 'UTC'))
    local_start = start_time.astimezone(local_tz)
    local_end = end_time.astimezone(local_tz)
    
    start_str = local_start.strftime("%H:%M %d/%m/%Y")
    end_str = local_end.strftime("%H:%M %d/%m/%Y")
    
    import os
    from urllib.parse import quote
    
    public_url = getattr(settings, 'PUBLIC_BASE_URL', 'https://webhook.socialai.id.vn').rstrip('/')
    banner_url = getattr(settings, 'DAILY_REPORT_BANNER_URL', "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=800&auto=format&fit=crop")
    
    # Try to find a local banner image in media/Baner Admin
    banner_dir = os.path.join(settings.MEDIA_ROOT, 'Baner Admin')
    if os.path.exists(banner_dir):
        files = [f for f in os.listdir(banner_dir) if os.path.isfile(os.path.join(banner_dir, f)) and not f.startswith('.')]
        if files:
            # Use the first valid file found
            local_file_name = files[0]
            banner_url = f"{public_url}{settings.MEDIA_URL}Baner%20Admin/{quote(local_file_name)}"
    
    zalo_channel = Channel.objects.filter(platform='zalo', is_active=True).first()
    if not zalo_channel or not zalo_channel.access_token:
        logger.error("Cannot send daily report: No active Zalo channel with access token")
        return {"status": "error", "reason": "no_zalo_channel"}

    sender = ZaloOASender()
    
    # ==========================
    # 1. ADMIN REPORT
    # ==========================
    admin_text = f"""📊 BÁO CÁO TỔNG QUAN 24H QUA 📊
(Từ {start_str} đến {end_str})

📥 TỔNG SỐ HỒ SƠ: {total}
- Qua Zalo: {zalo_count}
- Qua Facebook: {fb_count}

🚨 MỨC ĐỘ ƯU TIÊN:
- Cao: {high_count}
- Trung bình: {med_count}
- Thấp: {low_count}
- Khác: {unknown_count}

⚙️ TRẠNG THÁI XỬ LÝ (hồ sơ mới trong ngày):
- Chưa phân công: {unassigned_today}
- Chưa xử lý: {pending_today}
- Đang xử lý: {in_progress_today}
- Đã xử lý: {completed_today}
- Trả lại: {returned_today}

📌 Tổng số hồ sơ chưa phân công: {total_unassigned}"""

    admin_profiles = UserProfile.objects.filter(
        user__groups__name='Quản trị viên',
        user__is_active=True
    ).exclude(zalo_id="")
    
    sent_admins_count = 0
    for profile in admin_profiles:
        zalo_id = str(profile.zalo_id).strip()
        if not zalo_id:
            continue
        try:
            sender.send_media_template_message(
                access_token=zalo_channel.access_token,
                user_id=zalo_id,
                text=admin_text,
                image_url=banner_url
            )
            sent_admins_count += 1
        except Exception as e:
            logger.exception(f"Failed to send daily summary to admin {profile.user.username}: {e}")

    # ==========================
    # 2. SPECIALIST REPORT
    # ==========================
    specialist_profiles = UserProfile.objects.filter(
        user__groups__name='Chuyên viên',
        user__is_active=True
    ).exclude(zalo_id="")
    
    sent_specialists_count = 0
    for profile in specialist_profiles:
        zalo_id = str(profile.zalo_id).strip()
        if not zalo_id:
            continue
            
        sp_user = profile.user
        display_name = f"{sp_user.last_name} {sp_user.first_name}".strip() or sp_user.username
        
        assignments_24h = IntakeSubmissionAssignment.objects.filter(
            user=sp_user,
            created_at__gte=start_time,
            created_at__lt=end_time
        )
        
        total_assigned_24h = assignments_24h.count()
        role_main = assignments_24h.filter(role='main').count()
        role_co = assignments_24h.filter(role='co_handler').count()
        
        status_pending = assignments_24h.filter(status='pending').count()
        status_in_progress = assignments_24h.filter(status='in_progress').count()
        status_completed = assignments_24h.filter(status='completed').count()
        status_returned = assignments_24h.filter(status='returned').count()
        
        all_pending = IntakeSubmissionAssignment.objects.filter(user=sp_user, status='pending').count()
        all_in_progress = IntakeSubmissionAssignment.objects.filter(user=sp_user, status='in_progress').count()
        
        specialist_text = f"""📊 BÁO CÁO CÔNG VIỆC 24H QUA 📊
(Từ {start_str} đến {end_str})

👤 Chuyên viên: {display_name}

📥 HỒ SƠ ĐƯỢC GIAO TRONG 24H: {total_assigned_24h}
- Theo vai trò:
  + Tổng số hồ sơ được giao xử lý chính: {role_main}
  + Tổng số hồ sơ được giao phối hợp: {role_co}
- Theo trạng thái:
  + Chưa xử lý: {status_pending}
  + Đang xử lý: {status_in_progress}
  + Đã xử lý: {status_completed}
  + Trả lại: {status_returned}

⚙️ TỔNG SỐ HỒ SƠ CHƯA HOÀN THÀNH:
- Chưa xử lý: {all_pending}
- Đang xử lý: {all_in_progress}"""

        try:
            sender.send_media_template_message(
                access_token=zalo_channel.access_token,
                user_id=zalo_id,
                text=specialist_text,
                image_url=banner_url
            )
            sent_specialists_count += 1
        except Exception as e:
            logger.exception(f"Failed to send daily summary to specialist {sp_user.username}: {e}")

    return {
        "status": "success",
        "sent_admins": sent_admins_count,
        "total_admins": admin_profiles.count(),
        "sent_specialists": sent_specialists_count,
        "total_specialists": specialist_profiles.count(),
    }