import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def analyze_message_bridge(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    content = (data.get("content") or "").strip().lower()

    topic = "khác"
    sentiment = "trung lập"
    priority = "normal"
    summary = f"Khách gửi tin nhắn: {data.get('content', '')}"

    if any(keyword in content for keyword in ["giá", "bao nhiêu", "báo giá"]):
        topic = "hỏi giá"
    elif any(keyword in content for keyword in ["lỗi", "không được", "không đăng ký", "không vào được"]):
        topic = "hỗ trợ kỹ thuật"
        sentiment = "tiêu cực"
        priority = "high"
    elif any(keyword in content for keyword in ["khiếu nại", "phàn nàn", "bực", "tệ"]):
        topic = "khiếu nại"
        sentiment = "tiêu cực"
        priority = "high"
    elif any(keyword in content for keyword in ["cảm ơn", "ok", "được rồi"]):
        topic = "phản hồi tích cực"
        sentiment = "tích cực"

    return JsonResponse({
        "topic": topic,
        "sentiment": sentiment,
        "priority": priority,
        "summary": summary,
        "source": "internal_ai_bridge",
        "note": "Bước này đang là bridge nội bộ; bước sau sẽ thay bằng OpenClaw call thật."
    })