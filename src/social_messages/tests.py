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


from django.contrib.auth.models import Group, User
from social_messages.models import IntakeSubmission, IntakeSubmissionAssignment, UserProfile
from social_messages.services.admin_guard import AdminGuard
from social_messages.services.admin_submission_service import AdminSubmissionService
from social_messages.services.command_parser import CommandParser


class AdminCommandParserTest(TestCase):
    def setUp(self):
        self.parser = CommandParser()

    def test_parse_list_submissions(self):
        cases = [
            ("danh sách hồ sơ", "default"),
            ("danh sach ho so", "default"),
            ("hồ sơ của tôi", "default"),
            ("ho so cua toi", "default"),
            ("các hồ sơ", "default"),
            ("ds ho so", "default"),
            ("dshs", "default"),
            ("ho so", "default"),
            ("hồ sơ chưa phân công", "unassigned"),
            ("chưa phân công", "unassigned"),
            ("hồ sơ chưa xử lý", "pending"),
            ("chưa xử lý", "pending"),
            ("hồ sơ đang xử lý", "in_progress"),
            ("hồ sơ hôm nay", "today"),
            ("hồ sơ hôm qua", "yesterday"),
            ("hồ sơ khẩn cấp", "urgent"),
            ("hồ sơ ngày 02/09/2026", "specific_date"),
        ]
        for text, expected_filter in cases:
            res = self.parser.parse(text)
            self.assertTrue(res.get("is_command"), f"Failed for {text}")
            self.assertEqual(res.get("command_type"), "list_submissions", f"Wrong type for {text}")
            self.assertEqual(res.get("filter_type"), expected_filter, f"Wrong filter for {text}")

    def test_parse_submission_detail(self):
        cases = [
            ("xem hồ sơ 114", 114),
            ("xem ho so 114", 114),
            ("ho so 114", 114),
            ("hs 114", 114),
            ("hs#114", 114),
            ("xem ho so #999", 999),
            ("chi tiết hồ sơ 55", 55),
        ]
        for text, expected_id in cases:
            res = self.parser.parse(text)
            self.assertTrue(res.get("is_command"), f"Failed for {text}")
            self.assertEqual(res.get("command_type"), "submission_detail", f"Wrong type for {text}")
            self.assertEqual(res.get("submission_id"), expected_id, f"Wrong ID for {text}")

    def test_help_text_includes_submissions(self):
        help_text = self.parser.get_help_text()
        self.assertIn("hồ sơ", help_text.lower())


class AdminSubmissionServiceTest(TestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name="Quản trị viên")
        self.sp_group, _ = Group.objects.get_or_create(name="Chuyên viên")

        self.admin_user = User.objects.create(username="test_admin_user", is_superuser=True)
        self.admin_user.groups.add(self.admin_group)

        self.sp_user_1 = User.objects.create(username="specialist_1")
        self.sp_user_1.groups.add(self.sp_group)

        self.sp_user_2 = User.objects.create(username="specialist_2")
        self.sp_user_2.groups.add(self.sp_group)

        self.channel = Channel.objects.create(
            name="Zalo Test",
            platform="zalo",
            external_id="zalo_chan_1",
            is_active=True
        )
        self.conversation = Conversation.objects.create(
            channel=self.channel,
            customer_id="cust_1",
            status="open"
        )
        self.category = IntakeCategory.objects.create(
            name="Khiếu nại",
            code="complaint",
            is_active=True
        )

        self.sub_1 = IntakeSubmission.objects.create(
            conversation=self.conversation,
            category=self.category,
            intent="complaint",
            citizen_name="Nguyễn Văn A",
            phone_number="0912345678",
            content="Phản ánh ô nhiễm tiếng ồn",
            summary="Tiếng ồn tại khu dân cư",
            processing_status="pending",
            priority="urgent"
        )

        self.sub_2 = IntakeSubmission.objects.create(
            conversation=self.conversation,
            category=self.category,
            intent="complaint",
            citizen_name="Trần Thị B",
            phone_number="0987654321",
            content="Tranh chấp đất đai",
            summary="Tranh chấp đất",
            processing_status="in_progress",
            priority="normal"
        )

        # Phân công sub_1 cho specialist_1
        IntakeSubmissionAssignment.objects.create(
            submission=self.sub_1,
            user=self.sp_user_1,
            role="main",
            status="pending"
        )

        self.service = AdminSubmissionService()

    def test_format_submissions_list_options_1_and_3(self):
        # Kiểm tra hiển thị mặc định: Có bảng thống kê Option 3 + danh sách việc cần làm Option 1
        admin_text = self.service.format_submissions_list(self.admin_user, filter_type="default")
        self.assertIn("TỔNG QUAN HỒ SƠ TOÀN HỆ THỐNG", admin_text)
        self.assertIn("VIỆC CẦN XỬ LÝ NGAY", admin_text)
        self.assertIn("Nguyễn Văn A", admin_text)

        sp_text = self.service.format_submissions_list(self.sp_user_1, filter_type="default")
        self.assertIn("TỔNG QUAN HỒ SƠ CỦA BẠN", sp_text)
        self.assertIn("HỒ SƠ CẦN XỬ LÝ CỦA BẠN", sp_text)
        self.assertIn("Nguyễn Văn A", sp_text)

    def test_filter_by_status_and_date(self):
        # Lọc khẩn cấp (Option 1)
        urgent_text = self.service.format_submissions_list(self.admin_user, filter_type="urgent")
        self.assertIn("HỒ SƠ KHẨN CẤP", urgent_text)
        self.assertIn("Nguyễn Văn A", urgent_text)
        self.assertNotIn("Trần Thị B", urgent_text)

        # Lọc chưa xử lý
        pending_text = self.service.format_submissions_list(self.admin_user, filter_type="pending")
        self.assertIn("HỒ SƠ CHƯA XỬ LÝ", pending_text)
        self.assertIn("Nguyễn Văn A", pending_text)

    def test_specialist_cannot_view_unassigned(self):
        # Chuyên viên gõ lệnh xem chưa phân công -> bị thông báo chỉ dành cho Quản trị viên
        text = self.service.format_submissions_list(self.sp_user_1, filter_type="unassigned")
        self.assertIn("chỉ dành cho Quản trị viên", text)

    def test_admin_can_view_all_submissions(self):
        qs = self.service.get_submissions_queryset(self.admin_user)
        self.assertEqual(qs.count(), 2)

        has_access, text, sub = self.service.get_submission_detail(self.admin_user, self.sub_1.id)
        self.assertTrue(has_access)
        self.assertIn("Nguyễn Văn A", text)

        has_access, text, sub = self.service.get_submission_detail(self.admin_user, self.sub_2.id)
        self.assertTrue(has_access)
        self.assertIn("Trần Thị B", text)

    def test_specialist_permissions(self):
        # specialist_1 chỉ xem được sub_1
        qs1 = self.service.get_submissions_queryset(self.sp_user_1)
        self.assertEqual(qs1.count(), 1)
        self.assertEqual(qs1.first().id, self.sub_1.id)

        has_access, text, _ = self.service.get_submission_detail(self.sp_user_1, self.sub_1.id)
        self.assertTrue(has_access)

        # specialist_1 truy cập sub_2 -> bị từ chối
        has_access, text, _ = self.service.get_submission_detail(self.sp_user_1, self.sub_2.id)
        self.assertFalse(has_access)
        self.assertIn("không có quyền", text)

        # specialist_2 không được giao hồ sơ nào
        qs2 = self.service.get_submissions_queryset(self.sp_user_2)
        self.assertEqual(qs2.count(), 0)

    def test_collect_attachments(self):
        from datetime import timedelta
        # Thêm tin nhắn có ảnh vào hội thoại gửi trước khi sub_1 tạo
        Message.objects.create(
            platform_message_id="msg_att_1",
            conversation=self.conversation,
            sender_id="cust_1",
            sender_type="customer",
            message_type="image",
            content="",
            attachments=[{"type": "image", "url": "https://example.com/img1.jpg"}],
            sent_at=self.sub_1.created_at - timedelta(seconds=10)
        )

        atts = self.service.collect_submission_attachments(self.sub_1)
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]["url"], "https://example.com/img1.jpg")
        self.assertEqual(atts[0]["type"], "image")


class AdminGuardRoleTest(TestCase):
    def setUp(self):
        self.guard = AdminGuard()
        self.admin_group, _ = Group.objects.get_or_create(name="Quản trị viên")
        self.sp_group, _ = Group.objects.get_or_create(name="Chuyên viên")

        self.admin_user = User.objects.create(username="admin_guy", is_superuser=True)
        self.admin_user.groups.add(self.admin_group)
        UserProfile.objects.filter(user=self.admin_user).update(zalo_id="zalo_admin_99")

        self.sp_user = User.objects.create(username="sp_guy")
        self.sp_user.groups.add(self.sp_group)
        UserProfile.objects.filter(user=self.sp_user).update(zalo_id="zalo_sp_99")

        self.plain_user = User.objects.create(username="plain_guy")
        UserProfile.objects.filter(user=self.plain_user).update(zalo_id="zalo_plain_99")

    def test_guard_resolves_roles(self):
        # Admin
        u1 = self.guard.get_user_by_zalo_id("zalo_admin_99")
        self.assertEqual(u1, self.admin_user)
        self.assertTrue(self.guard.is_admin_user(u1))
        self.assertEqual(self.guard.get_user_role(u1), "admin")

        # Specialist
        u2 = self.guard.get_user_by_zalo_id("zalo_sp_99")
        self.assertEqual(u2, self.sp_user)
        self.assertTrue(self.guard.is_specialist_user(u2))
        self.assertEqual(self.guard.get_user_role(u2), "specialist")

        # Plain user without group
        u3 = self.guard.get_user_by_zalo_id("zalo_plain_99")
        self.assertEqual(u3, self.plain_user)
        self.assertEqual(self.guard.get_user_role(u3), "unauthorized")

        # Non-existent
        self.assertIsNone(self.guard.get_user_by_zalo_id("unknown_zalo"))


from unittest.mock import patch


class ProcessAdminCommandTaskTest(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(
            name="Zalo OA",
            platform="zalo",
            external_id="zalo_oa_1",
            access_token="test_token",
            is_active=True
        )
        self.conversation = Conversation.objects.create(
            channel=self.channel,
            customer_id="admin_zalo_123",
            status="open"
        )
        self.admin_group, _ = Group.objects.get_or_create(name="Quản trị viên")
        self.admin_user = User.objects.create(username="boss_admin", is_superuser=True)
        self.admin_user.groups.add(self.admin_group)
        UserProfile.objects.filter(user=self.admin_user).update(zalo_id="admin_zalo_123")

        self.category = IntakeCategory.objects.create(
            name="Tố giác",
            code="crime_report",
            is_active=True
        )
        self.sub = IntakeSubmission.objects.create(
            conversation=self.conversation,
            category=self.category,
            intent="crime_report",
            citizen_name="Lê Văn C",
            phone_number="0911223344",
            content="Nội dung tố giác trộm cắp",
            summary="Trộm cắp tài sản",
            processing_status="pending"
        )

    @patch("social_messages.services.outbound_message_service.OutboundMessageService.send_text")
    def test_task_list_submissions(self, mock_send_text):
        mock_send_text.return_value = {"status": "success"}

        from social_messages.tasks import process_admin_command
        msg = Message.objects.create(
            platform_message_id="cmd_msg_1",
            conversation=self.conversation,
            sender_id="admin_zalo_123",
            sender_type="admin",
            message_type="text",
            content="danh sách hồ sơ",
            sent_at=timezone.now()
        )

        res = process_admin_command(msg.id)
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("command_type"), "list_submissions")
        self.assertTrue(mock_send_text.called)
        sent_content = mock_send_text.call_args[0][1]
        self.assertIn("Lê Văn C", sent_content)

    @patch("social_messages.services.zalo_sender.ZaloOASender.send_attachment")
    @patch("social_messages.services.outbound_message_service.OutboundMessageService.send_text")
    def test_task_submission_detail_with_attachment(self, mock_send_text, mock_send_attachment):
        mock_send_text.return_value = {"status": "success"}
        mock_send_attachment.return_value = {"status": "success"}

        # Thêm ảnh vào hội thoại
        Message.objects.create(
            platform_message_id="att_msg_1",
            conversation=self.conversation,
            sender_id="admin_zalo_123",
            sender_type="customer",
            message_type="image",
            content="",
            attachments=[{"type": "image", "url": "https://example.com/evidence.jpg"}],
            sent_at=timezone.now()
        )

        from social_messages.tasks import process_admin_command
        msg = Message.objects.create(
            platform_message_id="cmd_msg_2",
            conversation=self.conversation,
            sender_id="admin_zalo_123",
            sender_type="admin",
            message_type="text",
            content=f"xem hồ sơ {self.sub.id}",
            sent_at=timezone.now()
        )

        res = process_admin_command(msg.id)
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("command_type"), "submission_detail")
        self.assertEqual(res.get("submission_id"), self.sub.id)
        self.assertTrue(mock_send_text.called)
        self.assertTrue(mock_send_attachment.called)


