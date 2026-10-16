from django.http import HttpResponse, JsonResponse
from social_messages.services.civic_heatmap_service import CivicHeatmapService

def civic_heatmap_api(request):
    """
    API cung cấp dữ liệu Không gian Bản đồ Tin báo Tội phạm & Khiếu nại từ hồ sơ thực tế
    phục vụ màn hình Giám sát Điều hành thông minh (VietMap / OpenStreetMap).
    """
    try:
        raw_days = request.GET.get("days", "30")
        days = int(raw_days)
        if days < 0 or days > 365:
            days = 30
    except (ValueError, TypeError):
        days = 30

    category_filter = request.GET.get("filter", "all")
    if category_filter not in ["all", "crime", "complaint", "completed"]:
        category_filter = "all"

    try:
        data = CivicHeatmapService.get_heatmap_data(days=days, category_filter=category_filter)
        return JsonResponse(data)
    except Exception as exc:
        return JsonResponse({
            "status": "error",
            "message": str(exc),
        }, status=500)


def privacy_policy(request):
    html = """
    <html>
    <head>
        <title>Chính sách quyền riêng tư</title>
    </head>
    <body>
        <h1>Chính sách quyền riêng tư</h1>

        <p>Ứng dụng Social AI Assistant thu thập và xử lý dữ liệu tin nhắn từ Facebook Messenger và Zalo nhằm mục đích hỗ trợ chăm sóc khách hàng.</p>

        <h2>Dữ liệu thu thập</h2>
        <ul>
            <li>ID người dùng</li>
            <li>Nội dung tin nhắn</li>
            <li>Thời gian gửi</li>
        </ul>

        <h2>Mục đích sử dụng</h2>
        <ul>
            <li>Phân tích nội dung tin nhắn</li>
            <li>Phản hồi tự động</li>
            <li>Tạo báo cáo</li>
        </ul>

        <h2>Bảo mật</h2>
        <p>Dữ liệu được lưu trữ an toàn và không chia sẻ với bên thứ ba.</p>

        <h2>Liên hệ</h2>
        <p>Email: buhoangdiep99@gmail.com</p>

    </body>
    </html>
    """
    return HttpResponse(html)