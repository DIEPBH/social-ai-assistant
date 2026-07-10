from social_messages.models import IntakeCategory, IntakeTemplate


class IntakeTemplateService:
    HEADER = (
        "CÔNG AN TỈNH THÁI NGUYÊN\n"
        "Hệ thống tiếp nhận và hỗ trợ thông tin\n\n"
    )

    @classmethod
    def get_active_categories(cls):
        return IntakeCategory.objects.filter(is_active=True).order_by("menu_order", "id")

    @classmethod
    def get_main_menu(cls):
        categories = list(cls.get_active_categories())

        if not categories:
            return (
                cls.HEADER
                + "Hiện hệ thống chưa có nhóm tiếp nhận nào đang hoạt động. "
                "Vui lòng liên hệ quản trị viên để cấu hình."
            )

        lines = [
            cls.HEADER.rstrip(),
            "",
            "Vui lòng chọn nhóm nội dung cần hỗ trợ:",
            "",
        ]

        for category in categories:
            lines.append(f"{category.selection_value}. {category.name}")

        valid_values = ", ".join(category.selection_value for category in categories)
        lines.extend([
            "",
            f"Vui lòng trả lời bằng số: {valid_values}.",
        ])
        return "\n".join(lines)

    @classmethod
    def get_invalid_menu(cls):
        categories = list(cls.get_active_categories())
        if not categories:
            return cls.get_main_menu()

        lines = [
            "Lựa chọn chưa hợp lệ.",
            "",
            "Vui lòng chọn một trong các nội dung sau:",
        ]
        for category in categories:
            lines.append(f"{category.selection_value}. {category.name}")
        lines.append("")
        lines.append("Bạn chỉ cần trả lời bằng số hoặc đúng tên nhóm cần hỗ trợ.")
        return "\n".join(lines)

    @classmethod
    def get_template(cls, category_or_code):
        category = cls._resolve_category(category_or_code)
        if not category:
            return cls.get_invalid_menu()

        template = (
            IntakeTemplate.objects.filter(category=category, is_active=True)
            .prefetch_related("fields")
            .order_by("id")
            .first()
        )
        if not template:
            return (
                f"MẪU TIẾP NHẬN {category.name.upper()}\n\n"
                "Nhóm tiếp nhận này chưa được cấu hình mẫu chi tiết. "
                "Vui lòng nhập đầy đủ thông tin liên quan đến nội dung cần phản ánh."
            )

        lines = [template.title.upper(), ""]
        if template.intro_text:
            lines.extend([template.intro_text.strip(), ""])

        active_fields = [field for field in template.fields.all() if field.is_active]
        for index, field in enumerate(active_fields, start=1):
            required_marker = " *" if field.is_required else ""
            lines.append(f"{index}. {field.label}{required_marker}:")
            if field.help_text:
                lines.append(f"   Gợi ý: {field.help_text}")

        if template.footer_text:
            lines.extend(["", template.footer_text.strip()])
        else:
            lines.extend(["", "Bạn có thể sao chép mẫu này và điền thông tin trực tiếp vào tin nhắn."])

        return "\n".join(lines)

    @classmethod
    def get_required_fields_template(cls, category_or_code):
        category = cls._resolve_category(category_or_code)
        if not category:
            return ""

        template = (
            IntakeTemplate.objects.filter(category=category, is_active=True)
            .prefetch_related("fields")
            .order_by("id")
            .first()
        )
        if not template:
            return ""

        lines = []
        active_fields = [field for field in template.fields.all() if field.is_active and field.is_required]
        for index, field in enumerate(active_fields, start=1):
            lines.append(f"{index}. {field.label}:")

        return "\n".join(lines)

    @classmethod
    def get_main_menu_buttons(cls):
        return [
            {
                "title": category.name,
                "type": "oa.query.show",
                "payload": category.selection_value,
            }
            for category in cls.get_active_categories()
        ]

    @classmethod
    def _resolve_category(cls, category_or_code):
        if isinstance(category_or_code, IntakeCategory):
            return category_or_code
        return IntakeCategory.objects.filter(code=category_or_code, is_active=True).first()
