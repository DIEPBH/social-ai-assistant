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

    MATCH_CONDITION_CHOICES = [
        ("==", "Chính xác (==)"),
        ("like", "Chứa từ khóa (like)"),
    ]

    template = models.ForeignKey(
        IntakeTemplate,
        on_delete=models.CASCADE,
        related_name="fields",
        verbose_name="Mẫu tiếp nhận",
    )
    match_condition = models.CharField(
        max_length=10,
        choices=MATCH_CONDITION_CHOICES,
        default="==",
        verbose_name="Điều kiện so sánh",
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
    state_entered_at = models.DateTimeField(blank=True, null=True, verbose_name="Thời điểm chuyển trạng thái")
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

    PROCESSING_STATUS_CHOICES = [
        ("unassigned", "Chưa phân công"),
        ("pending", "Chưa xử lý"),
        ("in_progress", "Đang xử lý"),
        ("completed", "Đã xử lý"),
        ("returned", "Trả lại"),
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
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="received", verbose_name="Trạng thái hệ thống")
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES, default="unassigned", verbose_name="Trạng thái xử lý")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")

    class Meta:
        db_table = "intake_submissions"
        verbose_name = "Hồ sơ phản ánh"
        verbose_name_plural = "Hồ sơ phản ánh"
        ordering = ["-created_at"]

    def __str__(self):
        category_name = self.category.name if self.category else self.intent
        return f"{category_name} - {self.citizen_name or self.conversation_id}"

class IntakeSubmissionAssignment(models.Model):
    ROLE_CHOICES = [
        ("main", "Xử lý chính"),
        ("co_handler", "Phối hợp"),
    ]
    STATUS_CHOICES = [
        ("pending", "Chưa xử lý"),
        ("in_progress", "Đang xử lý"),
        ("completed", "Đã xử lý"),
        ("returned", "Trả lại"),
    ]
    
    submission = models.ForeignKey(
        IntakeSubmission,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="Hồ sơ tiếp nhận"
    )
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="intake_assignments",
        verbose_name="Người xử lý"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="co_handler", verbose_name="Vai trò")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Trạng thái")
    return_reason = models.TextField(blank=True, default="", verbose_name="Lý do trả lại")
    processing_note = models.TextField(blank=True, default="", verbose_name="Thông tin xử lý")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày phân công")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        db_table = "intake_submission_assignments"
        verbose_name = "Phân công xử lý"
        verbose_name_plural = "Phân công xử lý"

    def __str__(self):
        return f"{self.get_role_display()} - {self.user.username}"

class IntakeSubmissionHistory(models.Model):
    ACTION_CHOICES = [
        ("assign", "Phân công xử lý"),
        ("accept", "Tiếp nhận hồ sơ"),
        ("return", "Trả lại hồ sơ"),
        ("complete", "Hoàn thành xử lý"),
    ]
    
    submission = models.ForeignKey(
        IntakeSubmission,
        on_delete=models.CASCADE,
        related_name="history",
        verbose_name="Hồ sơ tiếp nhận"
    )
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="intake_history",
        verbose_name="Người thực hiện"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Hành động")
    note = models.TextField(blank=True, default="", verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian")

    class Meta:
        db_table = "intake_submission_history"
        verbose_name = "Lịch sử xử lý"
        verbose_name_plural = "Lịch sử xử lý"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.submission.id} - {self.get_action_display()} - {self.user.username}"

class CustomerBlacklist(models.Model):
    customer_id = models.CharField(max_length=255, verbose_name="ID khách hàng", unique=True)
    customer_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Tên khách hàng")
    reason = models.TextField(blank=True, default="", verbose_name="Lý do chặn")
    is_active = models.BooleanField(default=True, verbose_name="Đang chặn")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày chặn")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        db_table = "customer_blacklist"
        verbose_name = "Danh sách chặn"
        verbose_name_plural = "Danh sách chặn"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer_name or self.customer_id} (Blocked)"


class IntegrationLog(models.Model):
    SYSTEM_CHOICES = [
        ("zalo_webhook", "Zalo Webhook"),
        ("facebook_webhook", "Facebook Webhook"),
        ("zalo_api", "Zalo API"),
        ("facebook_api", "Facebook API"),
        ("gemini_api", "Gemini API"),
        ("system", "Hệ thống"),
    ]
    DIRECTION_CHOICES = [
        ("inbound", "Gọi vào (Inbound)"),
        ("outbound", "Gọi ra (Outbound)"),
    ]

    system = models.CharField(max_length=50, choices=SYSTEM_CHOICES, verbose_name="Hệ thống")
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, verbose_name="Chiều gọi")
    endpoint = models.CharField(max_length=500, blank=True, default="", verbose_name="Endpoint/URL")
    method = models.CharField(max_length=20, blank=True, default="POST", verbose_name="Phương thức")
    status_code = models.IntegerField(null=True, blank=True, verbose_name="Mã HTTP")
    
    request_payload = models.JSONField(null=True, blank=True, verbose_name="Payload gửi đi/nhận vào")
    response_payload = models.JSONField(null=True, blank=True, verbose_name="Payload trả về")
    error_message = models.TextField(blank=True, default="", verbose_name="Thông báo lỗi")
    
    processing_time_ms = models.FloatField(null=True, blank=True, verbose_name="Thời gian xử lý (ms)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian tạo")

    class Meta:
        db_table = "integration_logs"
        verbose_name = "Lịch sử API (Integration Log)"
        verbose_name_plural = "Lịch sử API (Integration Logs)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.direction.upper()}] {self.system} - {self.status_code}"


from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile", verbose_name="Người dùng")
    zalo_id = models.CharField(max_length=100, blank=True, default="", verbose_name="Zalo ID")
    avatar = models.FileField(upload_to="avatars/", blank=True, null=True, verbose_name="Ảnh đại diện")

    class Meta:
        db_table = "user_profiles"
        verbose_name = "Hồ sơ người dùng"
        verbose_name_plural = "Hồ sơ người dùng"

    def __str__(self):
        return self.user.username


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
    else:
        if not hasattr(instance, "profile"):
            UserProfile.objects.create(user=instance)
        else:
            instance.profile.save()


@property
def user_avatar_property(self):
    try:
        if self.profile and self.profile.avatar:
            return self.profile.avatar
    except UserProfile.DoesNotExist:
        pass
    return "/static/images/default_avatar.jpg"

User.add_to_class("avatar", user_avatar_property)


from django.db.models.signals import pre_save, post_delete
import os

@receiver(pre_save, sender=UserProfile)
def auto_delete_file_on_change(sender, instance, **kwargs):
    """
    Deletes old file from filesystem when corresponding UserProfile object is updated with a new file.
    """
    if not instance.pk:
        return False

    try:
        old_profile = UserProfile.objects.get(pk=instance.pk)
    except UserProfile.DoesNotExist:
        return False

    old_avatar = old_profile.avatar
    new_avatar = instance.avatar
    if old_avatar and old_avatar != new_avatar:
        try:
            if os.path.isfile(old_avatar.path):
                os.remove(old_avatar.path)
        except Exception:
            pass


@receiver(post_delete, sender=UserProfile)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes file from filesystem when corresponding UserProfile object is deleted.
    """
    if instance.avatar:
        try:
            if os.path.isfile(instance.avatar.path):
                os.remove(instance.avatar.path)
        except Exception:
            pass

@receiver(post_delete, sender=Report)
def auto_delete_report_file_on_delete(sender, instance, **kwargs):
    """
    Deletes the generated report file from filesystem when corresponding Report object is deleted.
    """
    if instance.file_path:
        try:
            if os.path.isfile(instance.file_path):
                os.remove(instance.file_path)
        except Exception:
            pass


class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True, verbose_name="Mã cấu hình")
    value = models.TextField(blank=True, default="", verbose_name="Giá trị")
    is_active = models.BooleanField(default=True, verbose_name="Bật/Tắt")
    description = models.TextField(blank=True, default="", verbose_name="Mô tả")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        db_table = "system_configs"
        verbose_name = "Cấu hình hệ thống"
        verbose_name_plural = "Cấu hình hệ thống"

    def __str__(self):
        return f"{self.key} - {'BẬT' if self.is_active else 'TẮT'}"
