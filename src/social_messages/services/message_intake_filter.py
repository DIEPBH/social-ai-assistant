from dataclasses import dataclass, field
import re
import unicodedata

from django.db.models import Q

from social_messages.models import IntakeCategory, IntakeTemplate, IntakeValidationRule


@dataclass
class ValidationResult:
    is_valid: bool
    missing_fields: list[str] = field(default_factory=list)
    cleaned_data: dict = field(default_factory=dict)
    reason: str = ""


class MessageIntakeFilter:
    CORE_TARGET_FIELDS = {
        "citizen_name",
        "phone_number",
        "address",
        "content",
        "event_time",
        "event_location",
        "related_person",
        "urgency_level",
    }

    def validate(self, category_or_code, text: str) -> ValidationResult:
        category = self._resolve_category(category_or_code)
        if not category:
            return ValidationResult(is_valid=False, reason="unknown_category")

        template = (
            IntakeTemplate.objects.filter(category=category, is_active=True)
            .prefetch_related("fields")
            .order_by("id")
            .first()
        )
        if not template:
            return ValidationResult(is_valid=False, reason="missing_template")

        fields = [field for field in template.fields.all() if field.is_active]
        extracted, mapped_data, extra_data, labels = self._extract_fields(text, fields)

        missing = [
            field.label
            for field in fields
            if field.is_required and not extracted.get(field.field_key)
        ]
        if missing:
            return ValidationResult(
                is_valid=False,
                missing_fields=missing,
                cleaned_data=self._build_cleaned_data(extracted, mapped_data, extra_data, labels),
                reason="missing_required_fields",
            )

        rule_error = self._apply_rules(category, text, extracted, mapped_data)
        if rule_error:
            return ValidationResult(
                is_valid=False,
                missing_fields=[rule_error],
                cleaned_data=self._build_cleaned_data(extracted, mapped_data, extra_data, labels),
                reason="validation_rule_failed",
            )

        return ValidationResult(
            is_valid=True,
            cleaned_data=self._build_cleaned_data(extracted, mapped_data, extra_data, labels),
            reason="ok",
        )

    def _build_cleaned_data(self, extracted, mapped_data, extra_data, labels):
        return {
            "fields": extracted,
            "mapped_data": mapped_data,
            "extra_data": extra_data,
            "field_labels": labels,
        }

    def _extract_fields(self, text: str, fields) -> tuple[dict, dict, dict, dict]:
        lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
        extracted = {}
        mapped_data = {}
        extra_data = {}
        labels = {}

        for line in lines:
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            raw_key = key.strip()
            value = value.strip()
            if not value:
                continue

            field = self._match_field(raw_key, fields)
            if not field:
                continue

            extracted[field.field_key] = value
            labels[field.field_key] = field.label

            if field.target_field in self.CORE_TARGET_FIELDS:
                mapped_data[field.target_field] = value
            else:
                extra_data[field.field_key] = value

        return extracted, mapped_data, extra_data, labels

    def _match_field(self, raw_key: str, fields):
        normalized_key = self._normalize(raw_key)
        for field in fields:
            candidates = [field.label, field.field_key, *(field.aliases or [])]
            normalized_candidates = [self._normalize(c) for c in candidates if c]
            
            condition = getattr(field, 'match_condition', '==')
            if condition == 'like':
                for candidate in normalized_candidates:
                    if candidate in normalized_key or normalized_key in candidate:
                        return field
            else:
                if normalized_key in normalized_candidates:
                    return field
        return None

    def _apply_rules(self, category, raw_text, extracted, mapped_data):
        rules = IntakeValidationRule.objects.filter(
            Q(category__isnull=True) | Q(category=category),
            is_active=True,
        ).order_by("order", "id")

        for rule in rules:
            config = rule.config or {}
            message = rule.error_message or "Dữ liệu chưa hợp lệ"

            if rule.rule_type == "min_length":
                target = config.get("target", "raw_text")
                min_value = int(config.get("min", 0) or 0)
                value = self._get_value(target, raw_text, extracted, mapped_data)
                if len(value.strip()) < min_value:
                    return message

            elif rule.rule_type == "blocked_keywords":
                target = config.get("target", "raw_text")
                keywords = [str(k).lower() for k in config.get("keywords", [])]
                value = self._get_value(target, raw_text, extracted, mapped_data).lower()
                if any(keyword in value for keyword in keywords):
                    return message

            elif rule.rule_type == "regex":
                target = config.get("target", "raw_text")
                pattern = config.get("pattern", "")
                required = bool(config.get("required", True))
                value = self._get_value(target, raw_text, extracted, mapped_data)
                if pattern and required and not re.search(pattern, value):
                    return message

            elif rule.rule_type == "required_any":
                field_keys = config.get("fields", [])
                if not any(extracted.get(key) or mapped_data.get(key) for key in field_keys):
                    return message

        return None

    def _get_value(self, target, raw_text, extracted, mapped_data):
        if target == "raw_text":
            return raw_text or ""
        return str(extracted.get(target) or mapped_data.get(target) or "")

    def _resolve_category(self, category_or_code):
        if isinstance(category_or_code, IntakeCategory):
            return category_or_code
        return IntakeCategory.objects.filter(code=category_or_code, is_active=True).first()

    def _normalize(self, value: str) -> str:
        value = str(value or "").strip().lower()
        value = unicodedata.normalize("NFD", value)
        value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
        value = re.sub(r"[^a-z0-9\s_\-]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value
