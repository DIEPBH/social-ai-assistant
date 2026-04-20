import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.conf import settings
from social_messages.services.webhook_normalizer import WebhookNormalizer
from social_messages.models import Channel, Conversation, Message
from social_messages.tasks import process_message_analysis, process_admin_command


def save_incoming_message(data):
    platform = data["platform"]
    channel_external_id = data["channel_external_id"]
    customer_id = data["customer_id"]
    customer_name = data.get("customer_name")
    platform_message_id = data["platform_message_id"]
    sender_id = data["sender_id"]
    sender_type = data["sender_type"]
    message_type = data.get("message_type", "text")
    content = data.get("content", "")
    raw_payload = data.get("raw_payload", data)

    sent_at_str = data.get("sent_at")
    if sent_at_str:
        sent_at = parse_datetime(sent_at_str)
        if sent_at is None:
            sent_at = timezone.now()
    else:
        sent_at = timezone.now()

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
        }
    )

    if customer_name and conversation.customer_name != customer_name:
        conversation.customer_name = customer_name

    conversation.last_message_at = sent_at
    conversation.save()

    message, created = Message.objects.get_or_create(
        platform_message_id=platform_message_id,
        defaults={
            "conversation": conversation,
            "sender_id": sender_id,
            "sender_type": sender_type,
            "message_type": message_type,
            "content": content,
            "sent_at": sent_at,
            "raw_payload": raw_payload,
        }
    )

    analysis_task_id = None
    command_task_id = None

    if created:
        analysis_task = process_message_analysis.delay(message.id)
        analysis_task_id = analysis_task.id

        if platform == "zalo" and sender_type == "customer":
            command_task = process_admin_command.delay(message.id)
            command_task_id = command_task.id

    return {
        "message": message,
        "created": created,
        "analysis_task_id": analysis_task_id,
        "command_task_id": command_task_id,
        "conversation_id": conversation.id,
        "channel_id": channel.id,
    }


@csrf_exempt
def health_check(request):
    return JsonResponse({
        "status": "ok",
        "service": "webhooks",
    })


@csrf_exempt
def test_message_webhook(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Only POST method is allowed"},
            status=405,
        )

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Invalid JSON"},
            status=400,
        )

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
        result = save_incoming_message(data)
    except Channel.DoesNotExist:
        return JsonResponse(
            {"error": "Channel not found or inactive"},
            status=404,
        )

    return JsonResponse({
        "status": "success",
        "created": result["created"],
        "message_id": result["message"].id,
        "conversation_id": result["conversation_id"],
        "channel_id": result["channel_id"],
        "analysis_task_id": result["analysis_task_id"],
        "command_task_id": result["command_task_id"],
    })



@csrf_exempt
def facebook_webhook(request):
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

        saved_count = 0
        for item in normalized_messages:
            try:
                save_incoming_message(item)
                saved_count += 1
            except Channel.DoesNotExist:
                continue

        return JsonResponse({
            "status": "accepted",
            "saved_count": saved_count,
        }, status=200)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
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
        return JsonResponse({
            "status": "ignored",
            "reason": "unsupported_or_unmapped_payload",
            "payload_received": True,
        }, status=200)

    try:
        result = save_incoming_message(normalized)
    except Channel.DoesNotExist:
        return JsonResponse({"error": "Channel not found or inactive"}, status=404)

    return JsonResponse({
        "status": "accepted",
        "created": result["created"],
        "message_id": result["message"].id,
        "analysis_task_id": result["analysis_task_id"],
        "command_task_id": result["command_task_id"],
    }, status=200)



@csrf_exempt
def zalo_webhook_test(request):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    raw_body = request.body.decode("utf-8", errors="ignore").strip()

    # Cho phép body rỗng khi Zalo/Developer test webhook
    if not raw_body:
        return JsonResponse({"status": "ok", "message": "empty body accepted"}, status=200)

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        # Tạm thời vẫn trả 200 để vượt qua bước xác thực webhook
        return JsonResponse({"status": "ok", "message": "invalid json ignored"}, status=200)


    # TODO: xử lý payload thật ở đây
    return JsonResponse({"status": "ok"}, status=200)

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