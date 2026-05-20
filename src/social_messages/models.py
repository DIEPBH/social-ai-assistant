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


class IntakeCategory(models.Model):
    """
    Nhóm tiếp nhận động: thay cho hard-code complaint/crime_report/admin_procedure.
    Admin có thể thêm nhóm mới, đổi số chọn, đổi mẫu phản hồi mà không sửa code.
    """

    code = models.SlugField(max_length=80, unique=True, verbose_name="Mã nhóm")
    name = models.CharField(max_length=255, verbose_name="Tên nhóm")
    selection_value = models.CharField(max_length=20, unique=True, verbose_name="Giá trị người dân chọn")
    aliases = models.JSONField(default=list, blank=True, verbose_name="Từ khóa lựa chọn khác")
    description = models.TextField(blank=True, default="", verbose_name="Mô tả")
    menu_order = models.PositiveIntegerField(default=1, verbose_name="Thứ tự hiển thị")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    default_topic = models.CharField(max_length=255, blank=True, default="", verbose_name="Chủ đề mặc định")
    default_sentiment = models.CharField(max_length=50, blank=True, default="trung lập", verbose_name="Cảm xúc mặc định")
    default_priority = models.CharField(max_length=50, blank=True, default="normal", verbose_name="Ưu tiên mặc định")
    default_department = models.CharField(max_length=255, blank=True, default="", verbose_name="Bộ phận gợi ý")
    requires_human_review = models.BooleanField(default=True, verbose_name="Cần người rà soát")
    success_reply_text = models.TextField(blank=True, default="", verbose_name="Phản hồi sau khi tiếp nhận")
    urgent_reply_text = models.TextField(blank=True, default="", verbose_name="Phản hồi khi khẩn cấp")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        db_table = "intake_categories"
        verbose_name = "Nhóm tiếp nhận"
        verbose_name_plural = "Nhóm tiếp nhận"
        ordering = ["menu_order", "id"]

    def __str__(self):
        return f"{self.selection_value}. {self.name}"


class IntakeTemplate(models.Model):
    category = models.ForeignKey(
        IntakeCategory,
        on_delete=models.CASCADE,
        related_name="templates",
        verbose_name="Nhóm tiếp nhận",
    )
    title = models.CharField(max_length=255, verbose_name="Tiêu đề mẫu")
    intro_text = models.TextField(blank=True, default="", verbose_name="Mở đầu")
    footer_text = models.TextField(blank=True, default="", verbose_name="Kết thúc/hướng dẫn")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        db_table = "intake_templates"
        verbose_name = "Mẫu tiếp nhận"
        verbose_name_plural = "Mẫu tiếp nhận"
        ordering = ["category__menu_order", "id"]

    def __str__(self):
        return f"{self.category.name} - {self.title}"


class IntakeTemplateField(models.Model):
    TARGET_FIELD_CHOICES = [
        ("citizen_name", "Tên người dân"),
        ("phone_number", "Số điện thoại"),
        ("address", "Địa chỉ"),
        ("content", "Nội dung phản ánh"),
        ("event_time", "Thời gian xảy ra"),
        ("event_location", "Địa điểm"),
        ("related_person", "Người liên quan"),
        ("urgency_level", "Mức độ khẩn cấp"),
        ("extra_data", "Dữ liệu mở rộng/JSON"),
    ]

    FIELD_TYPE_CHOICES = [
        ("text", "Văn bản"),
        ("textarea", "Nội dung dài"),
        ("phone", "Số điện thoại"),
        ("datetime", "Thời gian"),
        ("choice", "Lựa chọn"),
    ]

    template = models.ForeignKey(
        IntakeTemplate,
        on_delete=models.CASCADE,
        related_name="fields",
        verbose_name="Mẫu tiếp nhận",
    )
    field_key = models.SlugField(max_length=80, verbose_name="Mã trường")
    label = models.CharField(max_length=255, verbose_name="Nhãn hiển thị")
    target_field = models.CharField(
        max_length=50,
        choices=TARGET_FIELD_CHOICES,
        default="extra_data",
        verbose_name="Ánh xạ vào cột",
    )
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default="text", verbose_name="Kiểu dữ liệu")
    is_required = models.BooleanField(default=True, verbose_name="Bắt buộc")
    aliases = models.JSONField(default=list, blank=True, verbose_name="Tên gọi khác")
    help_text = models.TextField(blank=True, default="", verbose_name="Gợi ý nhập")
    choice_options = models.JSONField(default=list, blank=True, verbose_name="Các lựa chọn")
    order = models.PositiveIntegerField(default=1, verbose_name="Thứ tự")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        db_table = "intake_template_fields"
        verbose_name = "Trường trong mẫu tiếp nhận"
        verbose_name_plural = "Trường trong mẫu tiếp nhận"
        ordering = ["order", "id"]
        unique_together = ("template", "field_key")

    def __str__(self):
        return f"{self.template.category.name} - {self.label}"


class IntakeValidationRule(models.Model):
    RULE_TYPE_CHOICES = [
        ("min_length", "Độ dài tối thiểu"),
        ("blocked_keywords", "Từ khóa bị chặn"),
        ("regex", "Kiểm tra regex"),
        ("required_any", "Bắt buộc một trong nhiều trường"),
    ]

    category = models.ForeignKey(
        IntakeCategory,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="validation_rules",
        verbose_name="Nhóm tiếp nhận",
        help_text="Để trống nếu áp dụng toàn hệ thống",
    )
    name = models.CharField(max_length=255, verbose_name="Tên luật")
    rule_type = models.CharField(max_length=50, choices=RULE_TYPE_CHOICES, verbose_name="Loại luật")
    config = models.JSONField(default=dict, blank=True, verbose_name="Cấu hình luật")
    error_message = models.TextField(blank=True, default="", verbose_name="Thông báo lỗi")
    order = models.PositiveIntegerField(default=1, verbose_name="Thứ tự")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        db_table = "intake_validation_rules"
        verbose_name = "Luật kiểm tra form"
        verbose_name_plural = "Luật kiểm tra form"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class KeywordRule(models.Model):
    MATCH_TYPE_CHOICES = [
        ("any_keyword", "Khớp một từ khóa bất kỳ"),
        ("all_keywords", "Khớp tất cả từ khóa"),
        ("regex", "Khớp regex"),
        ("always", "Luôn khớp"),
    ]

    category = models.ForeignKey(
        IntakeCategory,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="keyword_rules",
        verbose_name="Nhóm tiếp nhận",
        help_text="Để trống nếu áp dụng toàn hệ thống",
    )
    name = models.CharField(max_length=255, verbose_name="Tên luật keyword")
    match_type = models.CharField(max_length=50, choices=MATCH_TYPE_CHOICES, default="any_keyword", verbose_name="Kiểu khớp")
    keywords = models.JSONField(default=list, blank=True, verbose_name="Danh sách từ khóa")
    pattern = models.TextField(blank=True, default="", verbose_name="Regex nếu dùng")
    topic = models.CharField(max_length=255, blank=True, default="", verbose_name="Chủ đề")
    sentiment = models.CharField(max_length=50, blank=True, default="trung lập", verbose_name="Cảm xúc")
    priority = models.CharField(max_length=50, blank=True, default="normal", verbose_name="Độ ưu tiên")
    summary_template = models.TextField(blank=True, default="{content}", verbose_name="Mẫu tóm tắt")
    response_template = models.TextField(blank=True, default="", verbose_name="Mẫu phản hồi")
    result_payload = models.JSONField(default=dict, blank=True, verbose_name="Payload bổ sung")
    order = models.PositiveIntegerField(default=1, verbose_name="Thứ tự")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        db_table = "keyword_rules"
        verbose_name = "Luật keyword"
        verbose_name_plural = "Luật keyword"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class AdminCommand(models.Model):
    ACTION_CHOICES = [
        ("today_insight", "Tổng quan hôm nay"),
        ("system_status", "Trạng thái hệ thống"),
        ("generate_report", "Tạo báo cáo"),
        ("static_reply", "Trả lời cố định"),
    ]

    REPORT_PERIOD_CHOICES = [
        ("none", "Không áp dụng"),
        ("today", "Hôm nay"),
        ("yesterday", "Hôm qua"),
        ("current_week", "Tuần này"),
        ("current_month", "Tháng này"),
        ("specific_date", "Ngày cụ thể từ regex"),
    ]

    code = models.SlugField(max_length=80, unique=True, verbose_name="Mã lệnh")
    name = models.CharField(max_length=255, verbose_name="Tên lệnh")
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name="Hành động")
    report_period = models.CharField(max_length=30, choices=REPORT_PERIOD_CHOICES, default="none", verbose_name="Kỳ báo cáo")
    report_type = models.CharField(max_length=20, blank=True, default="", verbose_name="Loại báo cáo")
    report_title_template = models.CharField(max_length=255, blank=True, default="", verbose_name="Mẫu tiêu đề báo cáo")
    static_reply_text = models.TextField(blank=True, default="", verbose_name="Nội dung trả lời cố định")
    help_text = models.CharField(max_length=255, blank=True, default="", verbose_name="Gợi ý hiển thị")
    order = models.PositiveIntegerField(default=1, verbose_name="Thứ tự")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        db_table = "admin_commands"
        verbose_name = "Lệnh quản trị"
        verbose_name_plural = "Lệnh quản trị"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class AdminCommandPattern(models.Model):
    MATCH_TYPE_CHOICES = [
        ("exact", "Khớp chính xác"),
        ("contains", "Có chứa cụm từ"),
        ("regex", "Regex"),
    ]

    command = models.ForeignKey(
        AdminCommand,
        on_delete=models.CASCADE,
        related_name="patterns",
        verbose_name="Lệnh quản trị",
    )
    pattern_text = models.TextField(verbose_name="Mẫu câu")
    match_type = models.CharField(max_length=20, choices=MATCH_TYPE_CHOICES, default="contains", verbose_name="Kiểu khớp")
    priority = models.PositiveIntegerField(default=100, verbose_name="Độ ưu tiên")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        db_table = "admin_command_patterns"
        verbose_name = "Mẫu câu lệnh quản trị"
        verbose_name_plural = "Mẫu câu lệnh quản trị"
        ordering = ["priority", "id"]

    def __str__(self):
        return f"{self.command.name}: {self.pattern_text[:60]}"


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
    current_category = models.ForeignKey(
        IntakeCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_conversations",
        verbose_name="Nhóm tiếp nhận hiện tại",
    )
    current_intent = models.CharField(max_length=80, blank=True, default="", verbose_name="Mã nhóm cũ/tương thích")
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
    category = models.ForeignKey(
        IntakeCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="submissions",
        verbose_name="Nhóm tiếp nhận",
    )
    intent = models.CharField(max_length=80, verbose_name="Mã nhóm cũ/tương thích")

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

    raw_extracted_data = models.JSONField(default=dict, blank=True, verbose_name="Dữ liệu trích xuất")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="received", verbose_name="Trạng thái")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")

    class Meta:
        db_table = "intake_submissions"
        verbose_name = "Hồ sơ phản ánh"
        verbose_name_plural = "Hồ sơ phản ánh"
        ordering = ["-created_at"]

    def __str__(self):
        category_name = self.category.name if self.category else self.intent
        return f"{category_name} - {self.citizen_name or self.conversation_id}"
