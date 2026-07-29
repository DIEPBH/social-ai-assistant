# Hướng Dẫn Viết File `test.py` Cho Dự Án Social AI Assistant

Tài liệu này hướng dẫn chi tiết cách viết, tổ chức và thực thi các bài unit test / integration test cho dự án **Social AI Assistant** (Django 4.2+, PostgreSQL, Redis, Celery, Zalo OA / Facebook APIs, Gemini AI).

---

## 1. Tổng Quan Về Testing Trong Dự Án

- **Framework chính**: Django Test Suite dựa trên `unittest.TestCase` (`django.test.TestCase`).
- **Môi trường thực thi**: Các container Docker (`social_ai_web`, `social_ai_db`, `social_ai_redis`).
- **Vị trí file test**:
  - Mặc định của Django app: `src/<app_name>/tests.py` (ví dụ: `src/social_messages/tests.py`, `src/webhooks/tests.py`).
  - Dự án mở rộng: Tổ chức thành package `src/<app_name>/tests/` chứa các file theo module:
    - `test_models.py`
    - `test_services.py`
    - `test_views.py`
    - `test_tasks.py`

---

## 2. Các Lệnh Chạy Test (Execution Commands)

Vì dự án chạy trong Docker container, ta thực thi câu lệnh test qua `docker exec`:

### Chạy toàn bộ test trong dự án
```bash
docker exec social_ai_web python manage.py test
```

### Chạy test cho một App cụ thể
```bash
docker exec social_ai_web python manage.py test social_messages
docker exec social_ai_web python manage.py test webhooks
```

### Chạy một TestCase hoặc một hàm Test cụ thể
```bash
# Chạy 1 class TestCase
docker exec social_ai_web python manage.py test social_messages.tests.IntakeRouterMultiMessageTest

# Chạy 1 phương thức test cụ thể
docker exec social_ai_web python manage.py test social_messages.tests.IntakeRouterMultiMessageTest.test_accumulate_multiple_messages_then_finish
```

### Chạy với mức độ chi tiết log (Verbosity)
```bash
docker exec social_ai_web python manage.py test --verbosity 2
```

---

## 3. Cấu Trúc Chuẩn Của Một File Test

Một file test tiêu chuẩn tuân theo nguyên tắc **AAA (Arrange - Act - Assert)** và có cấu trúc như sau:

```python
from django.test import TestCase
from django.utils import timezone
from social_messages.models import Channel, Conversation

class ExampleServiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Khởi tạo dữ liệu dùng chung cho TẤT CẢ các test method trong class này.
        Dữ liệu này chỉ được tạo 1 lần -> Tối ưu tốc độ chạy test.
        (Chỉ dùng cho dữ liệu READ-ONLY).
        """
        cls.channel = Channel.objects.create(
            name="Zalo Test Channel",
            platform="zalo",
            external_id="zalo_channel_001",
            is_active=True
        )

    def setUp(self):
        """
        Khởi tạo dữ liệu riêng trước MỖI test method (mỗi hàm test chạy lại hàm này).
        Dùng khi dữ liệu bị thay đổi trong quá trình test.
        """
        self.conversation = Conversation.objects.create(
            channel=self.channel,
            customer_id="cust_999",
            status="open",
            current_state="awaiting_form",
            state_entered_at=timezone.now()
        )

    def test_example_feature_success(self):
        # 1. Arrange (Chuẩn bị dữ liệu / trạng thái)
        input_text = "Xin chào"

        # 2. Act (Thực hiện hành động cần test)
        result = self.conversation.status

        # 3. Assert (Kiểm tra kết quả)
        self.assertEqual(result, "open")
```

---

## 4. Các Kịch Bản Test Thực Tế Chi Tiết

### 4.1. Test Service Layer (Nghiệp Vụ Logic Core)
Ví dụ: Test `IntakeRouter` trong `social_messages/services/intake_router.py`.

```python
from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache
from social_messages.models import Channel, Conversation, IntakeCategory, IntakeTemplate, IntakeTemplateField, Message
from social_messages.services.intake_router import IntakeRouter

class IntakeRouterTest(TestCase):
    def setUp(self):
        cache.clear()  # Xóa cache trước mỗi test case để tránh ảnh hưởng bởi throttling logic
        
        self.channel = Channel.objects.create(
            name="Zalo OA Test",
            platform="zalo",
            external_id="zalo_123",
            is_active=True
        )
        self.category = IntakeCategory.objects.create(
            name="Báo cáo sự cố",
            code="incident_report",
            selection_value="1",
            is_active=True
        )
        self.conversation = Conversation.objects.create(
            channel=self.channel,
            customer_id="cust_001",
            status="open",
            current_state="awaiting_form",
            current_category=self.category,
            current_intent="incident_report",
            state_entered_at=timezone.now()
        )
        self.template = IntakeTemplate.objects.create(
            category=self.category,
            title="Mẫu báo cáo sự cố",
            is_active=True
        )
        IntakeTemplateField.objects.create(
            template=self.template,
            field_key="noidung",
            label="Nội dung",
            target_field="content",
            is_required=True,
            order=1
        )
        self.router = IntakeRouter()

    def test_single_message_full_data_saves_and_processes(self):
        # Giả lập tin nhắn chứa đầy đủ nội dung theo mẫu
        Message.objects.create(
            platform_message_id="msg_1001",
            conversation=self.conversation,
            sender_id="cust_001",
            sender_type="customer",
            message_type="text",
            content="Nội dung: Mất điện diện rộng",
            sent_at=timezone.now()
        )

        res = self.router.route(self.conversation, "Nội dung: Mất điện diện rộng")

        # Kiểm tra hành động trả về là save_and_process
        self.assertEqual(res["action"], "save_and_process")
        self.assertIn("Mất điện diện rộng", res["cleaned_data"]["mapped_data"]["content"])
```

---

### 4.2. Test API / Webhook Views (HTTP Requests)
Ví dụ: Test endpoint webhook nhận tin nhắn từ Zalo (`/webhooks/zalo/`).

```python
import json
from django.test import TestCase, Client
from unittest.mock import patch
from social_messages.models import Channel, Message

class ZaloWebhookViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.channel = Channel.objects.create(
            name="Zalo Official",
            platform="zalo",
            external_id="oa_zalo_123",
            is_active=True
        )

    @patch("webhooks.views.process_intake_submission.delay")
    def test_receive_zalo_user_message_success(self, mock_celery_task):
        payload = {
            "app_id": "oa_zalo_123",
            "sender": {"id": "user_456"},
            "recipient": {"id": "oa_zalo_123"},
            "event_name": "user_send_text",
            "message": {
                "msg_id": "zalo_msg_789",
                "text": "Xin chào hệ thống"
            },
            "timestamp": "1620000000"
        }

        # Gọi API webhook bằng POST request
        response = self.client.post(
            "/webhooks/zalo/",
            data=json.dumps(payload),
            content_type="application/json"
        )

        # Assert status code 200 OK
        self.assertEqual(response.status_code, 200)

        # Kiểm tra message đã được tạo trong Database
        msg_exists = Message.objects.filter(platform_message_id="zalo_msg_789").exists()
        self.assertTrue(msg_exists)
```

---

### 4.3. Test External APIs & Celery Tasks (Dùng `unittest.mock`)
Tuyệt đối **KHÔNG** gọi API thật ra bên ngoài (Zalo OA API, Gemini AI API) trong quá trình test. Hãy dùng `unittest.mock.patch`.

```python
from django.test import TestCase
from unittest.mock import patch, MagicMock
from social_messages.services.zalo_sender import ZaloSender
from social_messages.services.gemini_analyzer import GeminiAnalyzer

class ExternalServiceMockTest(TestCase):

    @patch("requests.post")
    def test_zalo_sender_post_request(self, mock_post):
        # Giả lập response từ requests.post
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": 0, "message": "Success"}
        mock_post.return_value = mock_response

        sender = ZaloSender(access_token="fake_token")
        result = sender.send_text_message(recipient_id="user_123", text="Hello")

        # Kiểm tra hàm post có được gọi đúng tham số không
        mock_post.assert_called_once()
        self.assertTrue(result)

    @patch("google.generativeai.GenerativeModel.generate_content")
    def test_gemini_analyzer(self, mock_generate):
        mock_generate.return_value.text = '{"category": "crime_report", "urgency": "high"}'

        analyzer = GeminiAnalyzer()
        analysis = analyzer.analyze("Có trộm đột nhập!")

        self.assertEqual(analysis["category"], "crime_report")
        self.assertEqual(analysis["urgency"], "high")
```

---

### 4.4. Test Cache & Throttling
Nếu có logic liên quan đến Redis/Django cache (ví dụ: giới hạn số lượng tin nhắn trong 5s):

```python
from django.test import TestCase
from django.core.cache import cache

class CacheThrottlingTest(TestCase):
    def tearDown(self):
        cache.clear()  # Dọn dẹp cache sau khi chạy xong test

    def test_throttling_logic(self):
        cache.set("user_throttle_cust_123", True, timeout=5)
        self.assertTrue(cache.get("user_throttle_cust_123"))

        # Giả lập trôi qua 5s bằng cách clear cache
        cache.clear()
        self.assertIsNone(cache.get("user_throttle_cust_123"))
```

---

## 5. Nguyên Tắc & Quy Định Viết Test (Best Practices)

1. **Tự chứa (Self-contained)**: Mỗi test case phải độc lập. Kết quả của test này không phụ thuộc vào thứ tự chạy hoặc dữ liệu của test khác.
2. **Quy tắc đặt tên hàm test**:
   - `test_<tên_chức_năng>_<kịch_bản>_<kết_quả>`
   - Ví dụ: `test_intake_router_missing_required_field_returns_reply_only()`
3. **Mock tất cả dịch vụ bên ngoài**:
   - Luôn mock `requests.get`, `requests.post`, Celery `.delay()`, Gemini API, Zalo/Facebook Graph API.
4. **Assert rõ ràng**:
   - `self.assertEqual(a, b)` thay vì `self.assertTrue(a == b)` (cho ra log chi tiết hơn khi fail).
   - `self.assertIn("chuỗi", text)`
   - `self.assertJSONEqual(response.content, expected_dict)`
   - `self.assertRaises(ValueError, func, arg)`
5. **Dọn dẹp Cache**: Luôn gọi `cache.clear()` trong `setUp` hoặc `tearDown` nếu test liên quan đến `django.core.cache`.

---

## 6. Kiểm Tra Và Báo Cáo Kết Quả

Khi bạn viết xong file `tests.py` hoặc thêm test method mới, hãy chạy lệnh kiểm tra trong Docker:

```bash
docker exec social_ai_web python manage.py test social_messages
```

Kỳ vọng đầu ra:
```text
Creating test database for alias 'default'...
Found X test(s).
System check identified no issues (0 silenced).
................
----------------------------------------------------------------------
Ran X tests in 0.123s

OK
Destroying test database for alias 'default'...
```
