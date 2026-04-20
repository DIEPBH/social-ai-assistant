from django.db import models

# Create your models here.


class Channel(models.Model):
    PLATFORM_CHOICES = [
        ("zalo", "Zalo OA"),
        ("facebook", "Facebook Messenger"),
    ]

    name = models.CharField(max_length=255)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    external_id = models.CharField(max_length=255, unique=True)
    access_token = models.TextField(blank=True, null=True)
    webhook_secret = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "channels"
        verbose_name = "Kênh"
        verbose_name_plural = "Kênh"

    def __str__(self):
        return f"{self.name} ({self.platform})"


class Conversation(models.Model):
    STATUS_CHOICES = [
        ("open", "Đang mở"),
        ("closed", "Đã đóng"),
        ("pending", "Chờ xử lý"),
    ]

    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    customer_id = models.CharField(max_length=255)
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    last_message_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations"
        verbose_name = "Hội thoại"
        verbose_name_plural = "Hội thoại"
        unique_together = ("channel", "customer_id")

    def __str__(self):
        return f"{self.customer_name or self.customer_id} - {self.channel.name}"


class Message(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ("text", "Text"),
        ("image", "Image"),
        ("file", "File"),
        ("audio", "Audio"),
        ("video", "Video"),
        ("other", "Other"),
    ]

    SENDER_TYPE_CHOICES = [
        ("customer", "Khách hàng"),
        ("page", "Page/OA"),
        ("system", "Hệ thống"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    platform_message_id = models.CharField(max_length=255, unique=True)
    sender_id = models.CharField(max_length=255)
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPE_CHOICES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default="text")
    content = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField()
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    topic = models.CharField(max_length=255, blank=True, null=True)
    sentiment = models.CharField(max_length=50, blank=True, null=True)
    priority = models.CharField(max_length=50, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    result_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, null=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "message_analyses"
        verbose_name = "Phân tích tin nhắn"
        verbose_name_plural = "Phân tích tin nhắn"

    def __str__(self):
        return f"Analysis for message {self.message_id} - {self.status}"

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

    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default="daily")
    title = models.CharField(max_length=255)
    from_time = models.DateTimeField()
    to_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "reports"
        verbose_name = "Báo cáo"
        verbose_name_plural = "Báo cáo"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.status}"