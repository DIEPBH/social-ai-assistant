from django.db import models


class Channel(models.Model):
    PLATFORM_CHOICES = [
        ("zalo", "Zalo OA"),
        ("facebook", "Facebook Messenger"),
    ]

    name = models.CharField(max_length=255, verbose_name="Tên kênh")
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, verbose_name="Nền tảng")
    external_id = models.CharField(max_length=255, unique=True, verbose_name="ID ngoài hệ thống")
    access_token = models.TextField(blank=True, null=True, verbose_name="Access Token")
    webhook_secret = models.CharField(max_length=255, blank=True, null=True, verbose_name="Webhook Secret")
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    refresh_token = models.TextField(blank=True, null=True, verbose_name="Refresh Token")
    access_token_expires_at = models.DateTimeField(blank=True, null=True, verbose_name="Hết hạn token")
    token_last_refreshed_at = models.DateTimeField(blank=True, null=True, verbose_name="Lần refresh gần nhất")

    class Meta:
        db_table = "channels"
        verbose_name = "Kênh tiếp nhận"
        verbose_name_plural = "Kênh tiếp nhận"

    def __str__(self):
        return f"{self.name} ({self.platform})"


class Conversation(models.Model):
    STATUS_CHOICES = [
        ("open", "Đang mở"),
        ("closed", "Đã đóng"),
        ("pending", "Chờ xử lý"),
    ]

    STATE_CHOICES = [
        ("", "Chưa khởi tạo"),
        ("awaiting_category_selection", "Chờ chọn nhóm yêu cầu"),
        ("awaiting_form", "Chờ nhập thông tin"),
    ]

    INTENT_CHOICES = [
        ("", "Chưa xác định"),
        ("complaint", "Khiếu nại"),
        ("crime_report", "Tin báo tội phạm"),
        ("admin_procedure", "Thủ tục hành chính"),
    ]

    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name="Kênh"
    )
    customer_id = models.CharField(max_length=255, verbose_name="ID khách hàng")
    customer_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Tên khách hàng")
    last_message_at = models.DateTimeField(blank=True, null=True, verbose_name="Tin nhắn cuối")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", verbose_name="Trạng thái")
    current_state = models.CharField(max_length=100, choices=STATE_CHOICES, blank=True, default="", verbose_name="Trạng thái luồng")
    current_intent = models.CharField(max_length=50, choices=INTENT_CHOICES, blank=True, default="", verbose_name="Loại yêu cầu")
    last_bot_prompt = models.TextField(blank=True, default="", verbose_name="Câu hỏi gần nhất của bot")
    form_retry_count = models.IntegerField(default=0, verbose_name="Số lần nhập lại form")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        db_table = "conversations"
        verbose_name = "Cuộc hội thoại"
        verbose_name_plural = "Cuộc hội thoại"
        unique_together = ("channel", "customer_id")

    def __str__(self):
        return f"{self.customer_name or self.customer_id} - {self.channel.name}"


class Message(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ("text", "Văn bản"),
        ("image", "Hình ảnh"),
        ("file", "Tệp"),
        ("audio", "Âm thanh"),
        ("video", "Video"),
        ("other", "Khác"),
    ]

    SENDER_TYPE_CHOICES = [
        ("customer", "Khách hàng"),
        ("page", "Page/OA"),
        ("system", "Hệ thống"),
        ("admin", "Quản trị viên"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Cuộc hội thoại"
    )
    platform_message_id = models.CharField(max_length=255, unique=True, verbose_name="ID tin nhắn nền tảng")
    sender_id = models.CharField(max_length=255, verbose_name="ID người gửi")
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPE_CHOICES, verbose_name="Loại người gửi")
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default="text", verbose_name="Loại tin nhắn")
    content = models.TextField(blank=True, null=True, verbose_name="Nội dung")
    sent_at = models.DateTimeField(verbose_name="Thời gian gửi")
    raw_payload = models.JSONField(default=dict, blank=True, verbose_name="Dữ liệu thô")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")

    class Meta:
        db_table = "messages"
        verbose_name = "Tin nhắn"
        verbose_name_plural = "Tin nhắn"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.platform_message_id} - {self.sender_type}"


class MessageAnalysis(models.Model):
    STATUS_CHOICES = [
        ("pending", "Đang chờ"),
        ("processed", "Đã xử lý"),
        ("failed", "Thất bại"),
    ]

    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name="analysis",
        verbose_name="Tin nhắn"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Trạng thái")
    topic = models.CharField(max_length=255, blank=True, null=True, verbose_name="Chủ đề")
    sentiment = models.CharField(max_length=50, blank=True, null=True, verbose_name="Cảm xúc")
    priority = models.CharField(max_length=50, blank=True, null=True, verbose_name="Độ ưu tiên")
    summary = models.TextField(blank=True, null=True, verbose_name="Tóm tắt")
    result_payload = models.JSONField(default=dict, blank=True, verbose_name="Kết quả AI")
    error_message = models.TextField(blank=True, null=True, verbose_name="Lỗi")
    processed_at = models.DateTimeField(blank=True, null=True, verbose_name="Thời gian xử lý")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")

    class Meta:
        db_table = "message_analyses"
        verbose_name = "Phân tích AI"
        verbose_name_plural = "Phân tích AI"

    def __str__(self):
        return f"Phân tích {self.message_id}"


class Report(models.Model):
    REPORT_TYPE_CHOICES = [
        ("daily", "Báo cáo ngày"),
        ("custom", "Báo cáo tùy chọn"),
    ]

    STATUS_CHOICES = [
        ("pending", "Đang chờ"),
        ("processing", "Đang xử lý"),
        ("completed", "Hoàn tất"),
        ("failed", "Thất bại"),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default="daily", verbose_name="Loại báo cáo")
    title = models.CharField(max_length=255, verbose_name="Tiêu đề")
    from_time = models.DateTimeField(verbose_name="Từ thời gian")
    to_time = models.DateTimeField(verbose_name="Đến thời gian")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Trạng thái")
    file_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="Đường dẫn file")
    file_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Tên file")
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="Hoàn thành lúc")

    class Meta:
        db_table = "reports"
        verbose_name = "Báo cáo"
        verbose_name_plural = "Báo cáo"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title}"


class IntakeSubmission(models.Model):
    INTENT_CHOICES = [
        ("complaint", "Khiếu nại"),
        ("crime_report", "Tin báo tội phạm"),
        ("admin_procedure", "Thủ tục hành chính"),
    ]

    STATUS_CHOICES = [
        ("received", "Đã tiếp nhận"),
        ("validated", "Hợp lệ"),
        ("analyzed", "Đã phân tích"),
        ("responded", "Đã phản hồi"),
        ("rejected", "Không hợp lệ"),
    ]

    conversation = models.ForeignKey(
        "social_messages.Conversation",
        on_delete=models.CASCADE,
        related_name="intake_submissions",
        verbose_name="Cuộc hội thoại"
    )
    message = models.ForeignKey(
        "social_messages.Message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intake_submissions",
        verbose_name="Tin nhắn nguồn"
    )
    intent = models.CharField(max_length=50, choices=INTENT_CHOICES, verbose_name="Loại phản ánh")

    citizen_name = models.CharField(max_length=255, blank=True, default="", verbose_name="Tên người dân")
    phone_number = models.CharField(max_length=50, blank=True, default="", verbose_name="Số điện thoại")
    address = models.TextField(blank=True, default="", verbose_name="Địa chỉ")
    content = models.TextField(verbose_name="Nội dung phản ánh")
    event_time = models.CharField(max_length=255, blank=True, default="", verbose_name="Thời gian xảy ra")
    event_location = models.TextField(blank=True, default="", verbose_name="Địa điểm")
    related_person = models.TextField(blank=True, default="", verbose_name="Người liên quan")
    urgency_level = models.CharField(max_length=50, blank=True, default="", verbose_name="Mức độ khẩn cấp")

    topic = models.CharField(max_length=255, blank=True, default="", verbose_name="Chủ đề")
    sentiment = models.CharField(max_length=50, blank=True, default="", verbose_name="Cảm xúc")
    priority = models.CharField(max_length=50, blank=True, default="", verbose_name="Độ ưu tiên")
    summary = models.TextField(blank=True, default="", verbose_name="Tóm tắt")
    response_text = models.TextField(blank=True, default="", verbose_name="Phản hồi")

    raw_extracted_data = models.JSONField(default=dict, blank=True, verbose_name="Dữ liệu AI trích xuất")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="received", verbose_name="Trạng thái")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")

    class Meta:
        db_table = "intake_submissions"
        verbose_name = "Hồ sơ phản ánh"
        verbose_name_plural = "Hồ sơ phản ánh"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_intent_display()} - {self.citizen_name or self.conversation_id}"