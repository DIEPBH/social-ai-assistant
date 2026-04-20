from django.http import HttpResponse

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