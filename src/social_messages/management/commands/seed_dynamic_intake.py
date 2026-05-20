from django.core.management.base import BaseCommand

from social_messages.models import (
    AdminCommand,
    AdminCommandPattern,
    IntakeCategory,
    IntakeTemplate,
    IntakeTemplateField,
    IntakeValidationRule,
    KeywordRule,
)


class Command(BaseCommand):
    help = "Seed dữ liệu mặc định cho luồng tiếp nhận động"

    def handle(self, *args, **options):
        self.seed_categories()
        self.seed_admin_commands()
        self.stdout.write(self.style.SUCCESS("Đã seed dữ liệu luồng tiếp nhận động."))

    def seed_categories(self):
        complaint = self.upsert_category(
            code="complaint",
            name="Khiếu nại",
            selection_value="1",
            aliases=["khieu nai", "khiếu nại", "phan anh", "phản ánh"],
            description="Tiếp nhận nội dung khiếu nại, phản ánh của người dân.",
            menu_order=1,
            default_topic="khiếu nại",
            default_priority="normal",
            default_department="bo_phan_tiep_nhan_khieu_nai",
            success_reply_text=(
                "Hệ thống đã tiếp nhận nội dung khiếu nại của anh/chị. "
                "Thông tin đã được chuyển đến bộ phận tiếp nhận để rà soát."
            ),
            urgent_reply_text=(
                "Hệ thống đã tiếp nhận nội dung khiếu nại khẩn cấp của anh/chị. "
                "Thông tin sẽ được ưu tiên chuyển đến bộ phận phụ trách."
            ),
        )
        self.upsert_template(
            complaint,
            title="Mẫu tiếp nhận khiếu nại",
            intro="Vui lòng cung cấp thông tin theo mẫu dưới đây:",
            footer="Bạn có thể sao chép mẫu này và điền thông tin trực tiếp vào tin nhắn.",
            fields=[
                (1, "citizen_name", "Họ và tên", "citizen_name", True, ["họ tên", "ho ten", "họ và tên"]),
                (2, "phone_number", "Số điện thoại", "phone_number", True, ["số điện thoại", "so dien thoai", "điện thoại", "phone"]),
                (3, "address", "Địa chỉ liên hệ", "address", False, ["địa chỉ", "dia chi", "địa chỉ liên hệ"]),
                (4, "content", "Nội dung khiếu nại", "content", True, ["nội dung", "nội dung khiếu nại", "noi dung khieu nai"]),
                (5, "event_time", "Thời gian xảy ra vụ việc", "event_time", True, ["thời gian", "thoi gian", "thời gian xảy ra"]),
                (6, "event_location", "Địa điểm xảy ra vụ việc", "event_location", True, ["địa điểm", "dia diem", "địa điểm xảy ra"]),
                (7, "attachments", "Tài liệu, hình ảnh đính kèm nếu có", "extra_data", False, ["tài liệu", "hình ảnh", "file đính kèm"]),
            ],
        )

        crime = self.upsert_category(
            code="crime_report",
            name="Tin báo tội phạm",
            selection_value="2",
            aliases=["tin bao toi pham", "tin báo tội phạm", "to giac", "tố giác"],
            description="Tiếp nhận tin báo, tố giác vi phạm, vụ việc có dấu hiệu tội phạm.",
            menu_order=2,
            default_topic="tin báo tội phạm",
            default_priority="normal",
            default_department="co_quan_cong_an",
            success_reply_text="Hệ thống đã tiếp nhận tin báo của anh/chị và sẽ chuyển xử lý theo quy trình.",
            urgent_reply_text=(
                "Hệ thống đã tiếp nhận tin báo. Nếu tình huống đang khẩn cấp hoặc đe dọa trực tiếp đến an toàn, "
                "vui lòng liên hệ ngay cơ quan công an hoặc số khẩn cấp tại địa phương."
            ),
        )
        self.upsert_template(
            crime,
            title="Mẫu tiếp nhận tin báo tội phạm",
            intro="Vui lòng cung cấp thông tin càng đầy đủ càng tốt:",
            footer="Trường hợp vụ việc đang diễn ra hoặc có nguy hiểm trực tiếp, vui lòng liên hệ ngay cơ quan công an gần nhất.",
            fields=[
                (1, "citizen_name", "Họ và tên người báo tin", "citizen_name", True, ["họ tên", "họ và tên", "họ tên người báo tin"]),
                (2, "phone_number", "Số điện thoại liên hệ", "phone_number", True, ["số điện thoại", "số điện thoại liên hệ", "phone"]),
                (3, "address", "Địa chỉ liên hệ", "address", False, ["địa chỉ", "địa chỉ liên hệ"]),
                (4, "content", "Nội dung vụ việc", "content", True, ["nội dung", "nội dung vụ việc", "noi dung vu viec"]),
                (5, "event_time", "Thời gian phát hiện hoặc xảy ra vụ việc", "event_time", True, ["thời gian", "thời gian phát hiện", "thời gian xảy ra"]),
                (6, "event_location", "Địa điểm xảy ra vụ việc", "event_location", True, ["địa điểm", "địa điểm xảy ra"]),
                (7, "related_person", "Đối tượng liên quan nếu biết", "related_person", False, ["đối tượng liên quan", "người liên quan"]),
                (8, "urgency_level", "Mức độ khẩn cấp", "urgency_level", False, ["mức độ khẩn cấp", "khẩn cấp"]),
                (9, "attachments", "Tài liệu, hình ảnh, video đính kèm nếu có", "extra_data", False, ["tài liệu", "hình ảnh", "video", "file đính kèm"]),
            ],
        )

        procedure = self.upsert_category(
            code="admin_procedure",
            name="Hỏi thủ tục hành chính",
            selection_value="3",
            aliases=["thu tuc", "thủ tục", "hanh chinh", "hành chính"],
            description="Tiếp nhận câu hỏi về thủ tục hành chính.",
            menu_order=3,
            default_topic="thủ tục hành chính",
            default_priority="normal",
            default_department="bo_phan_thu_tuc_hanh_chinh",
            success_reply_text="Hệ thống đã tiếp nhận câu hỏi về thủ tục hành chính của anh/chị.",
        )
        self.upsert_template(
            procedure,
            title="Mẫu hỏi thủ tục hành chính",
            intro="Vui lòng cung cấp thông tin theo mẫu dưới đây:",
            footer="Hệ thống sẽ tiếp nhận và phân loại nội dung để hỗ trợ bạn.",
            fields=[
                (1, "citizen_name", "Họ và tên", "citizen_name", True, ["họ tên", "họ và tên"]),
                (2, "phone_number", "Số điện thoại", "phone_number", True, ["số điện thoại", "điện thoại", "phone"]),
                (3, "procedure_name", "Thủ tục cần hỏi", "extra_data", True, ["thủ tục", "thủ tục cần hỏi"]),
                (4, "content", "Nội dung cần hỗ trợ", "content", True, ["nội dung", "nội dung cần hỗ trợ"]),
                (5, "related_unit", "Đơn vị hoặc địa phương liên quan", "extra_data", False, ["đơn vị", "địa phương", "đơn vị liên quan"]),
            ],
        )

        self.upsert_validation_rule(
            name="Chặn nội dung test quá ngắn",
            rule_type="blocked_keywords",
            config={"target": "raw_text", "keywords": ["test", "hello"]},
            error_message="Nội dung có vẻ là tin nhắn thử nghiệm. Vui lòng nhập thông tin theo đúng mẫu.",
            order=1,
        )

        self.upsert_keyword_rule(
            category=crime,
            name="Tin báo khẩn cấp",
            match_type="any_keyword",
            keywords=["vũ khí", "đe dọa", "đánh nhau", "cháy", "nổ", "bắt cóc", "khẩn cấp", "dao", "súng"],
            topic="an ninh trật tự",
            sentiment="tiêu cực",
            priority="high",
            order=1,
            response_template=crime.urgent_reply_text,
        )
        self.upsert_keyword_rule(
            category=crime,
            name="Tin báo tội phạm chung",
            match_type="always",
            keywords=[],
            topic="tin báo tội phạm",
            sentiment="tiêu cực",
            priority="normal",
            order=20,
            response_template=crime.success_reply_text,
        )
        self.upsert_keyword_rule(
            category=procedure,
            name="Thủ tục cư trú hộ khẩu",
            match_type="any_keyword",
            keywords=["hộ khẩu", "cư trú"],
            topic="thủ tục cư trú",
            sentiment="trung lập",
            priority="normal",
            order=10,
        )
        self.upsert_keyword_rule(
            category=procedure,
            name="Hộ tịch khai sinh",
            match_type="any_keyword",
            keywords=["khai sinh"],
            topic="hộ tịch khai sinh",
            sentiment="trung lập",
            priority="normal",
            order=11,
        )
        self.upsert_keyword_rule(
            category=complaint,
            name="Khiếu nại khẩn cấp",
            match_type="any_keyword",
            keywords=["khẩn cấp", "gấp", "nghiêm trọng", "ngay lập tức"],
            topic="khiếu nại khẩn cấp",
            sentiment="tiêu cực",
            priority="high",
            order=10,
            response_template=complaint.urgent_reply_text,
        )
        self.upsert_keyword_rule(
            category=complaint,
            name="Khiếu nại chung",
            match_type="any_keyword",
            keywords=["khiếu nại", "phản ánh", "không giải quyết", "chậm xử lý"],
            topic="khiếu nại",
            sentiment="tiêu cực",
            priority="normal",
            order=20,
            response_template=complaint.success_reply_text,
        )

    def seed_admin_commands(self):
        today = self.upsert_admin_command(
            code="today_insight",
            name="Tổng quan hôm nay",
            action="today_insight",
            help_text="tình hình hôm nay",
            order=1,
        )
        self.upsert_patterns(today, [
            ("contains", "tình hình hôm nay"),
            ("contains", "tinh hinh hom nay"),
            ("contains", "hôm nay thế nào"),
            ("contains", "tong quan hom nay"),
        ])

        status = self.upsert_admin_command(
            code="system_status",
            name="Kiểm tra trạng thái hệ thống",
            action="system_status",
            help_text="hệ thống có lỗi không",
            order=2,
        )
        self.upsert_patterns(status, [
            ("contains", "hệ thống có lỗi không"),
            ("contains", "kiểm tra hệ thống"),
            ("contains", "trạng thái hệ thống"),
            ("contains", "system status"),
        ])

        report_today = self.upsert_admin_command(
            code="report_today",
            name="Tạo báo cáo hôm nay",
            action="generate_report",
            report_period="today",
            report_type="daily",
            report_title_template="Báo cáo ngày {date}",
            help_text="báo cáo hôm nay",
            order=10,
        )
        self.upsert_patterns(report_today, [
            ("contains", "báo cáo hôm nay"),
            ("contains", "bao cao hom nay"),
            ("contains", "report today"),
        ])

        report_yesterday = self.upsert_admin_command(
            code="report_yesterday",
            name="Tạo báo cáo hôm qua",
            action="generate_report",
            report_period="yesterday",
            report_type="daily",
            report_title_template="Báo cáo ngày {date}",
            help_text="báo cáo hôm qua",
            order=11,
        )
        self.upsert_patterns(report_yesterday, [
            ("contains", "báo cáo hôm qua"),
            ("contains", "bao cao hom qua"),
            ("contains", "report yesterday"),
        ])

        report_week = self.upsert_admin_command(
            code="report_this_week",
            name="Tạo báo cáo tuần này",
            action="generate_report",
            report_period="current_week",
            report_type="custom",
            report_title_template="Báo cáo tuần {from_date} đến {to_date}",
            help_text="báo cáo tuần này",
            order=12,
        )
        self.upsert_patterns(report_week, [
            ("contains", "báo cáo tuần này"),
            ("contains", "bao cao tuan nay"),
            ("contains", "report this week"),
        ])

        report_month = self.upsert_admin_command(
            code="report_this_month",
            name="Tạo báo cáo tháng này",
            action="generate_report",
            report_period="current_month",
            report_type="custom",
            report_title_template="Báo cáo tháng {month_year}",
            help_text="báo cáo tháng này",
            order=13,
        )
        self.upsert_patterns(report_month, [
            ("contains", "báo cáo tháng này"),
            ("contains", "bao cao thang nay"),
            ("contains", "report this month"),
        ])

        specific = self.upsert_admin_command(
            code="report_specific_date",
            name="Tạo báo cáo ngày cụ thể",
            action="generate_report",
            report_period="specific_date",
            report_type="daily",
            report_title_template="Báo cáo ngày {date}",
            help_text="báo cáo ngày 29/04/2026",
            order=14,
        )
        self.upsert_patterns(specific, [
            ("regex", r"báo cáo ngày\s+(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{4})"),
            ("regex", r"bao cao ngay\s+(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{4})"),
        ])

    def upsert_category(self, **kwargs):
        obj, _ = IntakeCategory.objects.update_or_create(
            code=kwargs["code"],
            defaults=kwargs,
        )
        return obj

    def upsert_template(self, category, title, intro, footer, fields):
        template, _ = IntakeTemplate.objects.update_or_create(
            category=category,
            title=title,
            defaults={
                "intro_text": intro,
                "footer_text": footer,
                "is_active": True,
            },
        )
        for order, key, label, target, required, aliases in fields:
            IntakeTemplateField.objects.update_or_create(
                template=template,
                field_key=key,
                defaults={
                    "order": order,
                    "label": label,
                    "target_field": target,
                    "is_required": required,
                    "aliases": aliases,
                    "is_active": True,
                },
            )
        return template

    def upsert_validation_rule(self, **kwargs):
        IntakeValidationRule.objects.update_or_create(
            name=kwargs["name"],
            defaults=kwargs,
        )

    def upsert_keyword_rule(self, **kwargs):
        KeywordRule.objects.update_or_create(
            name=kwargs["name"],
            defaults=kwargs,
        )

    def upsert_admin_command(self, **kwargs):
        obj, _ = AdminCommand.objects.update_or_create(
            code=kwargs["code"],
            defaults=kwargs,
        )
        return obj

    def upsert_patterns(self, command, patterns):
        for index, (match_type, pattern_text) in enumerate(patterns, start=1):
            AdminCommandPattern.objects.update_or_create(
                command=command,
                pattern_text=pattern_text,
                defaults={
                    "match_type": match_type,
                    "priority": index,
                    "is_active": True,
                },
            )
