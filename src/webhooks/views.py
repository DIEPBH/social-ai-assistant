import json
import logging
logger = logging.getLogger(__name__)

from django.shortcuts import render
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from social_messages.models import Channel, Conversation, IntakeCategory, IntakeSubmission, Message, IntegrationLog, CustomerBlacklist
from social_messages.services.intake_router import IntakeRouter
from social_messages.services.outbound_message_service import OutboundMessageService
from social_messages.services.webhook_normalizer import WebhookNormalizer
from social_messages.tasks import process_intake_submission, process_admin_command
from social_messages.services.admin_guard import AdminGuard
import time
from functools import wraps

def log_integration_webhook(system_name):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            start_time = time.time()
            try:
                body = request.body.decode("utf-8")
                request_payload = json.loads(body) if body else {}
            except Exception:
                request_payload = {"raw_body": request.body.decode("utf-8", errors="replace")}
            
            error_message = ""
            try:
                response = view_func(request, *args, **kwargs)
            except Exception as e:
                error_message = str(e)
                raise
            finally:
                processing_time_ms = (time.time() - start_time) * 1000
                
                if 'response' in locals():
                    status_code = response.status_code
                    try:
                        response_payload = json.loads(response.content.decode("utf-8")) if response.content else {}
                    except Exception:
                        response_payload = {"raw_content": response.content.decode("utf-8", errors="replace")}
                else:
                    status_code = 500
                    response_payload = {}

                IntegrationLog.objects.create(
                    system=system_name,
                    direction="inbound",
                    endpoint=request.path,
                    method=request.method,
                    status_code=status_code,
                    request_payload=request_payload,
                    response_payload=response_payload,
                    error_message=error_message,
                    processing_time_ms=processing_time_ms
                )
            
            return response
        return _wrapped_view
    return decorator


def landing_page(request):
    return render(request, "landing/index.html")


@csrf_exempt
def health_check(request):
    return JsonResponse({
        "status": "ok",
        "service": "webhooks",
    })


@csrf_exempt
def test_message_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    required_fields = [
        "platform",
        "channel_external_id",
        "customer_id",
        "platform_message_id",
        "sender_id",
        "sender_type",
        "content",
    ]

    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return JsonResponse(
            {
                "error": "Missing required fields",
                "missing_fields": missing_fields,
            },
            status=400,
        )

    try:
        result = handle_incoming(data)
    except Channel.DoesNotExist:
        return JsonResponse({"error": "Channel not found or inactive"}, status=404)
    except Exception as exc:
        logger.exception("test_message_webhook failed")
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(result, status=200)


@csrf_exempt
@log_integration_webhook("facebook_webhook")
def facebook_webhook(request):
    logger.info("FACEBOOK WEBHOOK HIT method=%s body=%s", request.method, request.body.decode("utf-8"))
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        verify_token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and verify_token == settings.FACEBOOK_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type="text/plain")

        return JsonResponse({"error": "Verification failed"}, status=403)

    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        normalizer = WebhookNormalizer()
        normalized_messages = normalizer.normalize_facebook_message(payload)

        processed_count = 0
        failed_count = 0

        for item in normalized_messages:
            try:
                handle_incoming(item)
                processed_count += 1
            except Channel.DoesNotExist:
                failed_count += 1
                logger.warning("Facebook channel not found for payload: %s", item)
            except Exception:
                failed_count += 1
                logger.exception("facebook_webhook failed for one message")

        return JsonResponse(
            {
                "status": "accepted",
                "processed_count": processed_count,
                "failed_count": failed_count,
            },
            status=200,
        )

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
@log_integration_webhook("zalo_webhook")
def zalo_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    normalizer = WebhookNormalizer()
    normalized = normalizer.normalize_zalo_message(payload)
    
    if not normalized:
        logger.warning("Zalo payload ignored because it could not be normalized: %s", payload)
        return JsonResponse(
            {
                "status": "ignored",
                "reason": "unsupported_or_unmapped_payload",
                "payload_received": True,
            },
            status=200,
        )

    try:
        result = handle_incoming(normalized)
    except Channel.DoesNotExist:
        return JsonResponse({"error": "Channel not found or inactive"}, status=404)
    except Exception as exc:
        logger.exception("zalo_webhook failed")
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(result, status=200)


@csrf_exempt
def zalo_oauth_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")
    error = request.GET.get("error")

    return JsonResponse({
        "status": "ok",
        "code": code,
        "state": state,
        "error": error,
        "full_query": request.GET.dict(),
    })

def handle_incoming(payload):
    sender_id = payload.get("sender_id", "")
    platform = payload.get("platform", "")
    logger.warning("sender_id: %s", sender_id)
    
    conversation = get_or_create_conversation(payload)
    user_text = extract_user_text(payload)
    guard = AdminGuard()
    
    is_admin = guard.is_admin_message(
        platform=platform,
        sender_id=sender_id,
    )
    
    if is_admin:
        return handle_admin_incoming(conversation, payload, user_text)

    # 1. Blacklist check
    if CustomerBlacklist.objects.filter(customer_id=sender_id, is_active=True).exists():
        cache_key = f"notified_blacklist_{sender_id}"
        if not cache.get(cache_key):
            reply_text = "Tài khoản của bạn đã bị chặn do vi phạm quy định của hệ thống (Spam). Bạn không thể gửi thêm yêu cầu."
            send_reply_to_platform(conversation, reply_text)
            cache.set(cache_key, True, timeout=86400) # Notify once per 24 hours
        return {"status": "ignored", "reason": "blacklisted", "conversation_id": conversation.id}

    # 2. Rate Limit check
    rate_key = f"rate_limit_{sender_id}"
    block_key = f"temp_block_{sender_id}"
    
    if cache.get(block_key):
        return {"status": "ignored", "reason": "temp_blocked", "conversation_id": conversation.id}

    try:
        current_count = cache.incr(rate_key)
    except ValueError:
        cache.set(rate_key, 1, timeout=60)
        current_count = 1

    if current_count > 10:
        if current_count == 11:
            cache.set(block_key, True, timeout=300) # Block for 5 minutes
            reply_text = "Bạn đang gửi tin nhắn quá nhanh. Hệ thống tạm thời chặn tin nhắn của bạn trong 5 phút do nghi ngờ Spam."
            send_reply_to_platform(conversation, reply_text)
        return {"status": "ignored", "reason": "rate_limited", "conversation_id": conversation.id}

    return handle_citizen_incoming(conversation, payload, user_text)

def handle_admin_incoming(conversation, payload, user_text):
    sent_at = parse_sent_at(payload.get("sent_at"))

    message, created = Message.objects.get_or_create(
        platform_message_id=payload.get("platform_message_id", ""),
        defaults={
            "conversation": conversation,
            "sender_id": payload.get("sender_id", ""),
            "sender_type": payload.get("sender_type", "admin"),
            "message_type": payload.get("message_type", "text"),
            "content": user_text,
            "attachments": payload.get("attachments", []),
            "sent_at": sent_at,
            "raw_payload": payload.get("raw_payload", payload),
        },
    )
    task = process_admin_command.delay(message.id)

    return {
        "status": "admin_queued",
        "created": created,
        "message_id": message.id,
        "task_id": task.id,
        "conversation_id": conversation.id,
    }


def handle_citizen_incoming(conversation, payload, user_text):
    sent_at = parse_sent_at(payload.get("sent_at"))

    message, created = Message.objects.get_or_create(
        platform_message_id=payload.get("platform_message_id", ""),
        defaults={
            "conversation": conversation,
            "sender_id": payload.get("sender_id", ""),
            "sender_type": "admin" if AdminGuard().is_zalo_admin(payload.get("sender_id", "")) else "customer",
            "message_type": payload.get("message_type", "text"),
            "content": user_text,
            "attachments": payload.get("attachments", []),
            "sent_at": sent_at,
            "raw_payload": payload.get("raw_payload", payload),
        },
    )

    if not created:
        return {
            "status": "ignored",
            "reason": "duplicate_message",
            "conversation_id": conversation.id,
        }

    if payload.get("message_type") in ["image", "video", "file", "audio"]:
        return {
            "status": "saved_no_reply",
            "reason": "media_message_no_auto_reply",
            "conversation_id": conversation.id,
        }

    router = IntakeRouter()
    route_result = router.route(conversation=conversation, user_text=user_text)

    if route_result["action"] == "reply_only":
        reply_text = route_result["reply_text"]
        outbound_result = send_reply_to_platform(
            conversation,
            reply_text,
            buttons=route_result.get("buttons"),
        )

        return {
            "status": "reply_only",
            "conversation_id": conversation.id,
            "reply_text": reply_text,
            "outbound_result": outbound_result,
        }

    if route_result["action"] == "save_and_process":

        cleaned = route_result["cleaned_data"]
        mapped = cleaned.get("mapped_data", {})
        extra = cleaned.get("extra_data", {})
        fields = cleaned.get("fields", {})

        category = IntakeCategory.objects.get(id=route_result["category_id"])

        submission = IntakeSubmission.objects.create(
            conversation=conversation,
            message=message,
            category=category,
            intent=category.code,
            citizen_name=mapped.get("citizen_name", ""),
            phone_number=mapped.get("phone_number", ""),
            address=mapped.get("address", ""),
            content=mapped.get("content", "") or user_text,
            event_time=mapped.get("event_time", ""),
            event_location=mapped.get("event_location", ""),
            related_person=mapped.get("related_person", ""),
            urgency_level=mapped.get("urgency_level", ""),
            topic="",
            sentiment="",
            priority="",
            summary="",
            response_text="",
            raw_extracted_data={
                "category": {
                    "id": category.id,
                    "code": category.code,
                    "name": category.name,
                },
                "fields": fields,
                "mapped_data": mapped,
                "extra_data": extra,
                "field_labels": cleaned.get("field_labels", {}),
                "raw_text": user_text,
            },
            status="validated",
        )

        conversation.current_state = ""
        conversation.current_category = None
        conversation.current_intent = ""
        conversation.form_retry_count = 0
        conversation.last_bot_prompt = ""
        conversation.state_entered_at = None
        conversation.save(update_fields=[
            "current_state",
            "current_category",
            "current_intent",
            "form_retry_count",
            "last_bot_prompt",
            "state_entered_at",
            "updated_at",
        ])

        task = process_intake_submission.delay(submission.id)

        return {
            "status": "saved_and_queued",
            "created": created,
            "message_id": message.id,
            "submission_id": submission.id,
            "task_id": task.id,
            "conversation_id": conversation.id,
            "category": category.code,
        }

    return {
        "status": "ignored",
        "reason": "unknown_route_action",
        "conversation_id": conversation.id,
    }

def get_or_create_conversation(data):
    platform = data["platform"]
    channel_external_id = data["channel_external_id"]
    customer_id = data["customer_id"]
    customer_name = data.get("customer_name", "")

    sent_at = parse_sent_at(data.get("sent_at"))

    channel = Channel.objects.get(
        external_id=channel_external_id,
        platform=platform,
        is_active=True,
    )

    conversation, _ = Conversation.objects.get_or_create(
        channel=channel,
        customer_id=customer_id,
        defaults={
            "customer_name": customer_name,
            "last_message_at": sent_at,
            "status": "open",
        },
    )

    updated_fields = []

    if customer_name and conversation.customer_name != customer_name:
        conversation.customer_name = customer_name
        updated_fields.append("customer_name")

    conversation.last_message_at = sent_at
    updated_fields.append("last_message_at")

    if updated_fields:
        updated_fields.append("updated_at")
        conversation.save(update_fields=updated_fields)

    if platform == "zalo" and not conversation.customer_name:
        from social_messages.tasks import fetch_zalo_user_profile
        fetch_zalo_user_profile.delay(conversation.id)

    return conversation


def extract_user_text(payload):
    return (payload.get("content") or "").strip()


def parse_sent_at(sent_at_str):
    if sent_at_str:
        sent_at = parse_datetime(sent_at_str)
        if sent_at is not None:
            return sent_at
    return timezone.now()


def send_reply_to_platform(conversation, reply_text, buttons=None):
    try:
        service = OutboundMessageService()
        if buttons:
            result = service.send_text_with_buttons(conversation, reply_text, buttons)
        else:
            result = service.send_text(conversation, reply_text)

        logger.info(
            "OUTBOUND REPLY platform=%s conversation_id=%s result=%s",
            conversation.channel.platform,
            conversation.id,
            result,
        )
        return result
    except Exception as exc:
        logger.exception(
            "Failed sending outbound reply platform=%s conversation_id=%s",
            conversation.channel.platform,
            conversation.id,
        )
        return {
            "status": "error",
            "error": str(exc),
        }

@csrf_exempt
def debug_conversation(request, customer_id):
    from social_messages.models import Conversation

    c = Conversation.objects.filter(customer_id=customer_id).last()

    if not c:
        return JsonResponse({"error": "not found"}, status=404)

    return JsonResponse({
        "id": c.id,
        "state": c.current_state,
        "intent": c.current_intent,
        "category_id": c.current_category_id,
        "category_name": c.current_category.name if c.current_category else "",
        "retry": c.form_retry_count,
    })