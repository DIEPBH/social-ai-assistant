import re
import unicodedata

from django.db.models import Q

from social_messages.models import KeywordRule


class KeywordEngine:
    def analyze_submission(self, submission):
        content = submission.content or ""
        category = getattr(submission, "category", None)

        rules = KeywordRule.objects.filter(is_active=True).filter(
            Q(category__isnull=True) | Q(category=category)
        ).order_by("order", "id")

        for rule in rules:
            if self._matches(rule, content):
                return self._build_result(rule, submission)

        return None

    def _matches(self, rule, content: str) -> bool:
        normalized = self._normalize(content)
        keywords = [self._normalize(keyword) for keyword in (rule.keywords or []) if str(keyword).strip()]

        if rule.match_type == "always":
            return True

        if rule.match_type == "any_keyword":
            return bool(keywords) and any(keyword in normalized for keyword in keywords)

        if rule.match_type == "all_keywords":
            return bool(keywords) and all(keyword in normalized for keyword in keywords)

        if rule.match_type == "regex":
            pattern = rule.pattern or ""
            return bool(pattern) and re.search(pattern, content, flags=re.IGNORECASE | re.UNICODE) is not None

        return False

    def _build_result(self, rule, submission):
        category = getattr(submission, "category", None)
        context = {
            "content": submission.content or "",
            "category": category.name if category else submission.intent,
            "category_code": category.code if category else submission.intent,
            "citizen_name": submission.citizen_name or "",
            "phone_number": submission.phone_number or "",
            "address": submission.address or "",
            "event_time": submission.event_time or "",
            "event_location": submission.event_location or "",
            "related_person": submission.related_person or "",
            "urgency_level": submission.urgency_level or "",
        }

        def render(template, fallback=""):
            if not template:
                return fallback
            try:
                return template.format(**context)
            except Exception:
                return template

        return {
            "matched": True,
            "engine": "keyword_engine",
            "selected_engine": "keyword_engine",
            "topic": rule.topic or (category.default_topic if category else "khác"),
            "sentiment": rule.sentiment or (category.default_sentiment if category else "trung lập"),
            "priority": rule.priority or (category.default_priority if category else "normal"),
            "summary": render(rule.summary_template, submission.content or ""),
            "response_text": render(rule.response_template, ""),
            "rule_name": rule.name,
            "rule_id": rule.id,
            "raw_result": {
                "rule_payload": rule.result_payload or {},
            },
        }

    def _normalize(self, value: str) -> str:
        value = str(value or "").strip().lower()
        value = unicodedata.normalize("NFD", value)
        value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
        value = re.sub(r"[^a-z0-9\s_\-]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value
