from django.test import TestCase
from django.utils import timezone
from social_messages.models import Channel, Conversation, IntakeCategory, IntakeTemplate, Message
from social_messages.services.intake_router import IntakeRouter

class IntakeRouterMultiMessageTest(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(
            name="Zalo Test",
            platform="zalo",
            external_id="zalo_123",
            is_active=True
        )
        self.conversation = Conversation.objects.create(
            channel=self.channel,
            customer_id="cust_123",
            status="open",
            current_state="awaiting_form",
            state_entered_at=timezone.now()
        )
        self.category = IntakeCategory.objects.create(
            name="Tố giác tội phạm",
            code="crime_report",
            is_active=True,
            selection_value="1"
        )
        self.template = IntakeTemplate.objects.create(
            category=self.category,
            title="Mẫu tố giác",
            is_active=True
        )
        from social_messages.models import IntakeTemplateField
        IntakeTemplateField.objects.create(
            template=self.template,
            field_key="noidung",
            label="Nội dung",
            target_field="content",
            is_required=True,
            order=1
        )
        self.conversation.current_category = self.category
        self.conversation.current_intent = self.category.code
        self.conversation.save()

        self.router = IntakeRouter()

    def test_accumulate_multiple_messages_then_finish(self):
        Message.objects.create(
            platform_message_id="msg_1",
            conversation=self.conversation,
            sender_id="cust_123",
            sender_type="customer",
            message_type="text",
            content="Xin chào, tôi muốn báo cáo.",
            sent_at=timezone.now()
        )
        res1 = self.router.route(self.conversation, "Xin chào, tôi muốn báo cáo.")
        self.assertEqual(res1["action"], "reply_only")
        self.assertIn("Các mục còn thiếu", res1["reply_text"])
        
        # Tin nhắn nhắn ngay lập tức (< 5s) sẽ bị throttle -> ignore
        Message.objects.create(
            platform_message_id="msg_2",
            conversation=self.conversation,
            sender_id="cust_123",
            sender_type="customer",
            message_type="text",
            content="Hôm qua có trộm.",
            sent_at=timezone.now()
        )
        res2 = self.router.route(self.conversation, "Hôm qua có trộm.")
        self.assertEqual(res2["action"], "ignore")

        # Giả lập > 5s trôi qua (xóa cache)
        from django.core.cache import cache
        cache.clear()

        Message.objects.create(
            platform_message_id="msg_2_2",
            conversation=self.conversation,
            sender_id="cust_123",
            sender_type="customer",
            message_type="text",
            content="Thêm thông tin.",
            sent_at=timezone.now()
        )
        res2_2 = self.router.route(self.conversation, "Thêm thông tin.")
        self.assertEqual(res2_2["action"], "reply_only")

        # Send 'xong' while still missing 'Nội dung:' mapping
        Message.objects.create(
            platform_message_id="msg_3",
            conversation=self.conversation,
            sender_id="cust_123",
            sender_type="customer",
            message_type="text",
            content="xong",
            sent_at=timezone.now()
        )
        res3 = self.router.route(self.conversation, "xong")
        self.assertEqual(res3["action"], "reply_only")
        self.assertIn("Nội dung chưa đúng mẫu", res3["reply_text"])

        # Now send the actual required field
        Message.objects.create(
            platform_message_id="msg_4",
            conversation=self.conversation,
            sender_id="cust_123",
            sender_type="customer",
            message_type="text",
            content="Nội dung: Hôm qua có trộm.",
            sent_at=timezone.now()
        )
        res4 = self.router.route(self.conversation, "Nội dung: Hôm qua có trộm.")
        self.assertEqual(res4["action"], "save_and_process")
        
        cleaned_content = res4["cleaned_data"]["mapped_data"]["content"]
        self.assertIn("Hôm qua có trộm", cleaned_content)

    def test_single_message_full_data_saves_and_processes(self):
        Message.objects.create(
            platform_message_id="msg_single",
            conversation=self.conversation,
            sender_id="cust_123",
            sender_type="customer",
            message_type="text",
            content="Nội dung: Trộm đột nhập ban đêm.",
            sent_at=timezone.now()
        )
        res = self.router.route(self.conversation, "Nội dung: Trộm đột nhập ban đêm.")
        self.assertEqual(res["action"], "save_and_process")
        self.assertIn("Trộm đột nhập ban đêm", res["cleaned_data"]["mapped_data"]["content"])
