from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    is_valid: bool
    missing_fields: list[str] = field(default_factory=list)
    cleaned_data: dict = field(default_factory=dict)
    reason: str = ""


class MessageIntakeFilter:
    REQUIRED_FIELDS = {
        "complaint": [
            "họ tên",
            "số điện thoại",
            "nội dung khiếu nại",
            "thời gian",
            "địa điểm",
        ],
        "crime_report": [
            "họ tên",
            "số điện thoại",
            "nội dung vụ việc",
            "thời gian",
            "địa điểm",
        ],
        "admin_procedure": [
            "họ tên",
            "số điện thoại",
            "thủ tục",
            "nội dung",
        ],
    }

    FIELD_ALIASES = {
        "họ tên": ["họ tên", "ho ten", "họ và tên", "Họ tên", "Họ tên người báo tin"],
        "số điện thoại": ["số điện thoại", "so dien thoai", "điện thoại", "phone"],
        "địa chỉ": ["địa chỉ", "dia chi"],
        "địa chỉ liên hệ": ["địa chỉ liên hệ", "dia chi lien he"],
        "nội dung khiếu nại": ["nội dung khiếu nại", "noi dung khieu nai"],
        "nội dung vụ việc": ["nội dung vụ việc", "noi dung vu viec"],
        "thời gian": ["thời gian", "thoi gian", "thời gian xảy ra", "thời gian phát hiện"],
        "địa điểm": ["địa điểm", "dia diem", "địa điểm xảy ra"],
        "thủ tục": ["thủ tục cần hỏi", "thủ tục", "thu tuc"],
        "nội dung": ["nội dung", "noi dung", "nội dung cần hỗ trợ"],
        "đối tượng liên quan": ["đối tượng liên quan", "doi tuong lien quan"],
        "mức độ khẩn cấp": ["mức độ khẩn cấp", "muc do khan cap"],
        "tài liệu đính kèm": ["tài liệu đính kèm", "tai lieu dinh kem"],
    }

    def validate(self, intent: str, text: str) -> ValidationResult:
        required_fields = self.REQUIRED_FIELDS.get(intent, [])
        if not required_fields:
            return ValidationResult(
                is_valid=False,
                reason="unknown_intent",
            )

        extracted = self._extract_fields(text)
        missing = [
            field for field in required_fields
            if field not in extracted or not extracted[field]
        ]

        if missing:
            return ValidationResult(
                is_valid=False,
                missing_fields=missing,
                cleaned_data=extracted,
                reason="missing_required_fields",
            )

        return ValidationResult(
            is_valid=True,
            missing_fields=[],
            cleaned_data=extracted,
            reason="ok",
        )

    def _extract_fields(self, text: str) -> dict:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        data = {}

        for line in lines:
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key_normalized = key.strip().lower()
            value = value.strip()

            canonical_key = self._map_to_canonical_field(key_normalized)
            if canonical_key and value:
                data[canonical_key] = value

        return data

    def _map_to_canonical_field(self, raw_key: str):
        for canonical, aliases in self.FIELD_ALIASES.items():
            for alias in aliases:
                if raw_key == alias.lower():
                    return canonical
        return None