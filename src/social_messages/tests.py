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


from unittest.mock import patch, MagicMock
from social_messages.models import PIIMaskingRule, SystemConfig
from social_messages.services.pii_masking_service import PIIMaskingService
from social_messages.services.gemini_analyzer import GeminiAnalyzer


class Decree13PIIMaskingAndConsentTest(TestCase):
    def setUp(self):
        PIIMaskingRule.objects.all().delete()
        PIIMaskingRule.objects.create(
            name="Số CCCD 12 số",
            rule_type="regex",
            pattern=r"\b\d{12}\b",
            token_prefix="CITIZEN_ID",
            priority=10,
            is_active=True,
        )
        PIIMaskingRule.objects.create(
            name="Số điện thoại VN",
            rule_type="regex",
            pattern=r"(?:\+84|84|0)(?:3[2-9]|5[2689]|7[06-9]|8[1-9]|9[0-9])\d{7}\b",
            token_prefix="PHONE",
            priority=20,
            is_active=True,
        )
        PIIMaskingRule.objects.create(
            name="Biển số xe",
            rule_type="regex",
            pattern=r"\b\d{2}[A-Z]\d?[-.\s]?(?:\d{4,5}|\d{3}\.\d{2})\b",
            token_prefix="VEHICLE_PLATE",
            priority=25,
            is_active=True,
        )
        PIIMaskingRule.objects.create(
            name="Họ và tên",
            rule_type="regex",
            pattern=r"(?i)\b(?:tôi\s+tên\s+là|tôi\s+là|tên\s+tôi\s+là)\s+([A-ZÀ-Ỹ][a-zà-ỹ]*(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]*){1,4})\b",
            token_prefix="PERSON_NAME",
            priority=30,
            is_active=True,
        )
        PIIMaskingRule.objects.create(
            name="Địa chỉ",
            rule_type="regex",
            pattern=r"(?i)\b(?:số\s+nhà\s+|số\s+)?\d+[/A-Za-z0-9\-_]*\s+(?:ngõ|ngách|hẻm|đường|phố)\s+[A-Za-z0-9À-ỹ\s]+?(?=(?:[.,;\n]|$))",
            token_prefix="ADDRESS",
            priority=40,
            is_active=True,
        )
        PIIMaskingService.invalidate_cache()

        self.channel = Channel.objects.create(
            name="Zalo Test Consent",
            platform="zalo",
            external_id="zalo_consent_1",
            is_active=True,
        )

    def test_pii_masking_and_demasking(self):
        raw_text = "Tôi là Hoàng Văn Nam, CCCD 001095012345, SĐT 0912345678, ở số 15 ngõ 42 Doãn Kế Thiện, biển xe 29A-123.45."
        masked, mapping = PIIMaskingService.mask_pii(raw_text, session_id="test_session_unit")

        # Đảm bảo không còn dữ liệu nhạy cảm dạng rõ trong văn bản sau khi mask
        self.assertNotIn("001095012345", masked)
        self.assertNotIn("0912345678", masked)
        self.assertNotIn("Hoàng Văn Nam", masked)
        self.assertNotIn("29A-123.45", masked)

        # Đảm bảo có chứa các Token
        self.assertIn("{{CITIZEN_ID_", masked)
        self.assertIn("{{PHONE_", masked)
        self.assertIn("{{PERSON_NAME_", masked)
        self.assertIn("{{ADDRESS_", masked)
        self.assertIn("{{VEHICLE_PLATE_", masked)

        # Giải mã lại
        demasked = PIIMaskingService.demask_data(masked, session_id="test_session_unit")
        self.assertEqual(demasked, raw_text)

    @patch.object(GeminiAnalyzer, "_call_api")
    def test_gemini_analyzer_receives_only_masked_prompt(self, mock_call_api):
        mock_call_api.return_value = {
            "topic": "an ninh trật tự",
            "sentiment": "tiêu cực",
            "priority": "high",
            "summary": "Công dân {{PERSON_NAME_#1}} phản ánh tại {{ADDRESS_#1}} kèm SĐT {{PHONE_#1}}",
        }

        analyzer = GeminiAnalyzer()
        raw_text = "Tôi là Nguyễn Văn B, SĐT 0988776655, ở số 10 ngõ 5 Cầu Giấy, có trộm đột nhập."
        result = analyzer.analyze_message(raw_text, session_id="session_gemini_test")

        # Kiểm tra prompt gửi tới _call_api
        called_prompt = mock_call_api.call_args[0][0]
        self.assertNotIn("0988776655", called_prompt)
        self.assertNotIn("Nguyễn Văn B", called_prompt)
        self.assertIn("{{PERSON_NAME_", called_prompt)
        self.assertIn("{{PHONE_", called_prompt)

        # Kiểm tra kết quả trả về đã được de-masking hoàn chỉnh
        self.assertIn("Nguyễn Văn B", result["summary"])
        self.assertIn("0988776655", result["summary"])
        self.assertNotIn("{{PERSON_NAME_", result["summary"])
        self.assertNotIn("{{PHONE_", result["summary"])

    @patch("requests.post")
    def test_gemini_analyzer_creates_integration_log_with_valid_system(self, mock_post):
        from social_messages.models import IntegrationLog
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": '{"topic": "hỏi đáp", "sentiment": "trung tính", "priority": "normal", "summary": "Nội dung"}'}]
                }
            }]
        }
        mock_post.return_value = mock_response

        analyzer = GeminiAnalyzer()
        analyzer.api_key = "fake_key"
        analyzer._call_api("prompt test", json_response=True)

        log = IntegrationLog.objects.filter(system="gemini_api").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.direction, "outbound")
        self.assertEqual(log.status_code, 200)
        self.assertNotIn("fake_key", log.endpoint)
        self.assertEqual(log.get_system_display(), "Gemini API")

    @patch("requests.post")
    def test_admin_ai_interpreter_creates_integration_log(self, mock_post):
        from social_messages.models import IntegrationLog
        from social_messages.services.admin_ai_interpreter import AdminAIInterpreter

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": '{"is_command": true, "command_type": "today_insight"}'}]
                }
            }]
        }
        mock_post.return_value = mock_response

        interpreter = AdminAIInterpreter()
        interpreter.api_key = "fake_admin_key"
        interpreter.url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=fake_admin_key"
        res = interpreter.interpret("hôm nay thế nào")

        self.assertTrue(res["is_command"])
        log = IntegrationLog.objects.filter(system="gemini_api", endpoint__contains="gemini-3.5-flash").first()
        self.assertIsNotNone(log)
        self.assertNotIn("fake_admin_key", log.endpoint)
        self.assertEqual(log.get_system_display(), "Gemini API")

    def test_consent_toggle_disabled_by_default(self):
        conv = Conversation.objects.create(
            channel=self.channel,
            customer_id="cust_consent_1",
            status="open",
        )
        self.assertFalse(conv.is_consent_nd13)

        # Khi cấu hình CONSENT_ND13_ENABLED tắt (mặc định)
        from webhooks.views import handle_citizen_incoming
        payload = {
            "platform": "zalo",
            "sender_id": "cust_consent_1",
            "platform_message_id": "consent_msg_1",
            "message_type": "text",
            "content": "Xin chào",
        }

        with patch("webhooks.views.send_reply_to_platform") as mock_reply:
            handle_citizen_incoming(conv, payload, "Xin chào")
            conv.refresh_from_db()
            self.assertTrue(conv.is_consent_nd13)
            # Không gửi tin nhắn xác nhận thừa thãi
            self.assertFalse(any("Nghị định 13" in str(c) for c in mock_reply.call_args_list))

    def test_consent_toggle_enabled(self):
        SystemConfig.objects.update_or_create(
            key="CONSENT_ND13_ENABLED",
            defaults={"is_active": True, "value": "true"},
        )
        conv = Conversation.objects.create(
            channel=self.channel,
            customer_id="cust_consent_2",
            status="open",
        )
        self.assertFalse(conv.is_consent_nd13)

        from webhooks.views import handle_citizen_incoming
        payload = {
            "platform": "zalo",
            "sender_id": "cust_consent_2",
            "platform_message_id": "consent_msg_2",
            "message_type": "text",
            "content": "Tôi muốn phản ánh",
        }

        with patch("webhooks.views.send_reply_to_platform") as mock_reply:
            handle_citizen_incoming(conv, payload, "Tôi muốn phản ánh")
            conv.refresh_from_db()
            self.assertTrue(conv.is_consent_nd13)
            # Phải có gửi thông báo Nghị định 13
            self.assertTrue(any("Nghị định 13" in str(c) for c in mock_reply.call_args_list))


class CivicHeatmapTest(TestCase):
    """Kiểm thử tính năng Bản đồ nhiệt Dân sinh chuẩn hóa Tháp Dân số (Per-Capita) và API GIS Đề án 06."""

    def setUp(self):
        from social_messages.models import AdministrativeArea, Channel, Conversation, IntakeCategory, IntakeSubmission
        self.area_dvh, _ = AdministrativeArea.objects.update_or_create(
            code="CG_DVH",
            defaults={
                "name": "Phường Dịch Vọng Hậu",
                "cluster": "Cầu Giấy",
                "city": "Hà Nội",
                "latitude": 21.0365,
                "longitude": 105.7865,
                "permanent_population": 30000,
                "temporary_population": 10000,
                "geojson_polygon": {
                    "type": "Polygon",
                    "coordinates": [[
                        [105.779, 21.031],
                        [105.794, 21.031],
                        [105.794, 21.042],
                        [105.779, 21.042],
                        [105.779, 21.031],
                    ]]
                },
                "is_active": True,
            }
        )
        self.channel = Channel.objects.create(
            name="Zalo Hotline",
            platform="zalo",
            external_id="zalo_hotline",
            is_active=True,
        )
        self.conversation = Conversation.objects.create(
            channel=self.channel,
            customer_id="citizen_demo_1",
            status="open",
        )
        self.category = IntakeCategory.objects.create(
            name="An ninh trật tự",
            code="antt",
            is_active=True,
        )

    def test_resolve_area_by_keyword(self):
        from social_messages.services.civic_heatmap_service import CivicHeatmapService
        # Nhận diện theo tên đường Duy Tân thuộc Dịch Vọng Hậu
        area = CivicHeatmapService.resolve_area(text="Phản ánh karaoke ồn ào ở phố Duy Tân")
        self.assertIsNotNone(area)
        self.assertEqual(area.code, "CG_DVH")

        # Nhận diện theo tên phường trực tiếp
        area2 = CivicHeatmapService.resolve_area(text="Địa chỉ: Phường Dịch Vọng Hậu, Cầu Giấy")
        self.assertIsNotNone(area2)
        self.assertEqual(area2.code, "CG_DVH")

    def test_resolve_area_by_coordinates(self):
        from social_messages.services.civic_heatmap_service import CivicHeatmapService
        # Tọa độ nằm trong Polygon của DVH
        area = CivicHeatmapService.resolve_area(latitude=21.0365, longitude=105.7865)
        self.assertIsNotNone(area)
        self.assertEqual(area.code, "CG_DVH")

        # Tọa độ bên ngoài
        area_out = CivicHeatmapService.resolve_area(latitude=20.500, longitude=106.000)
        self.assertIsNone(area_out)

    def test_crime_and_complaint_incident_generation(self):
        from social_messages.models import IntakeSubmission, SystemConfig
        from social_messages.services.civic_heatmap_service import CivicHeatmapService

        cat_crime = IntakeCategory.objects.create(name="Tin báo tội phạm", code="crime_report", selection_value="2", is_active=True)
        cat_complaint = IntakeCategory.objects.create(name="Khiếu nại tố giác", code="complaint", selection_value="3", is_active=True)

        SystemConfig.objects.create(
            key="VIETMAP_API_KEY",
            value="test_vietmap_key_xyz",
            description="VietMap Tile API Key",
            is_active=True,
        )

        # 5 hồ sơ tội phạm
        for i in range(5):
            IntakeSubmission.objects.create(
                conversation=self.conversation,
                category=cat_crime,
                area=self.area_dvh,
                citizen_name=f"Công dân Báo án {i}",
                urgency_level="high" if i < 2 else "medium",
                priority="high",
                processing_status="completed" if i == 4 else "in_progress",
                content=f"Tin báo tội phạm trộm cắp xe máy số {i}",
                status="responded",
            )

        # 3 hồ sơ khiếu nại
        for i in range(3):
            IntakeSubmission.objects.create(
                conversation=self.conversation,
                category=cat_complaint,
                area=self.area_dvh,
                citizen_name=f"Công dân Khiếu nại {i}",
                urgency_level="low",
                priority="medium",
                processing_status="pending",
                content=f"Khiếu nại trật tự đô thị lấn chiếm vỉa hè số {i}",
                status="received",
            )

        data = CivicHeatmapService.get_heatmap_data(days=7, category_filter="all")
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["vietmap_api_key"], "test_vietmap_key_xyz")
        self.assertTrue(data["has_vietmap"])
        self.assertEqual(data["summary"]["total_incidents"], 8)
        self.assertEqual(data["summary"]["crime_count"], 5)
        self.assertEqual(data["summary"]["complaint_count"], 3)
        self.assertEqual(data["summary"]["completed_count"], 1)
        self.assertEqual(len(data["incidents"]), 8)

        # Filter crime only
        data_crime_only = CivicHeatmapService.get_heatmap_data(days=7, category_filter="crime")
        self.assertEqual(len(data_crime_only["incidents"]), 5)

        # Filter complaint only
        data_complaint_only = CivicHeatmapService.get_heatmap_data(days=7, category_filter="complaint")
        self.assertEqual(len(data_complaint_only["incidents"]), 3)

    def test_civic_heatmap_api_endpoint(self):
        from django.urls import reverse
        url = reverse("civic_heatmap_api") + "?days=7&filter=all"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("summary", data)
        self.assertIn("incidents", data)
        self.assertIn("area_stats", data)
        self.assertIn("hourly_trend", data)
        self.assertIn("vietmap_api_key", data)

    def test_admin_dashboard_heatmap_context(self):
        from django.contrib.auth.models import User
        from django.urls import reverse
        admin_user = User.objects.create_superuser("admin_test", "admin@test.vn", "password123")
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("heatmap_data_json", response.context)
        self.assertContains(response, "civic-heatmap-map")
        self.assertContains(response, "crimeVsComplaintChart")
        self.assertContains(response, "incidentHourlyChart")

    def test_phu_xuyen_and_submission_geocoding(self):
        from unittest.mock import patch
        from social_messages.models import AdministrativeArea, IntakeSubmission, IntakeCategory
        from social_messages.services.civic_heatmap_service import CivicHeatmapService

        area_px = AdministrativeArea.objects.filter(code="TN_52").first()
        if not area_px:
            area_px = AdministrativeArea.objects.create(
                code="TN_52",
                name="Xã Phú Xuyên",
                cluster="Cụm Phía Tây",
                city="Thái Nguyên",
                latitude=21.6641,
                longitude=105.5541,
            )

        cat_crime = IntakeCategory.objects.first()
        sub = IntakeSubmission.objects.create(
            conversation=self.conversation,
            category=cat_crime,
            area=area_px,
            citizen_name="Đoàn Quảng Đông",
            address="xóm khuôn muống xã phú xuyên",
            event_location="tại nhà",
            content="bị đe doạ tống tiền",
        )

        # Test fallback khi không có API Key
        lat, lng, name = CivicHeatmapService.resolve_submission_coordinates(sub, vietmap_api_key="")
        self.assertAlmostEqual(lat, 21.6641, places=3)
        self.assertAlmostEqual(lng, 105.5541, places=3)
        self.assertEqual(name, "Xã Phú Xuyên")

        # Test khi có VietMap API trả về tọa độ chi tiết xóm Khuôn Muống
        with patch.object(CivicHeatmapService, "_geocode_via_vietmap", return_value=(21.678652, 105.517733, "Xóm Khuôn Muống, Xã Phú Xuyên")):
            lat_vm, lng_vm, name_vm = CivicHeatmapService.resolve_submission_coordinates(sub, vietmap_api_key="mock_key")
            self.assertAlmostEqual(lat_vm, 21.678652, places=4)
            self.assertAlmostEqual(lng_vm, 105.517733, places=4)
            self.assertIn("Khuôn Muống", name_vm)





