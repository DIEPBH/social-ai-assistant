import re
import unicodedata

from django.utils import timezone

from social_messages.models import IntakeCategory
from social_messages.services.intake_template_service import IntakeTemplateService
from social_messages.services.message_intake_filter import MessageIntakeFilter


class IntakeRouter:
    def __init__(self):
        self.template_service = IntakeTemplateService()
        self.intake_filter = MessageIntakeFilter()

    def detect_category(self, text: str):
        normalized = self._normalize(text)
        if not normalized:
            return None

        for category in IntakeCategory.objects.filter(is_active=True).order_by("menu_order", "id"):
            candidates = [
                category.selection_value,
                category.code,
                category.name,
                *(category.aliases or []),
            ]
            normalized_candidates = {self._normalize(value) for value in candidates if value}
            if normalized in normalized_candidates:
                return category

        return None

    def route(self, conversation, user_text: str):
        if not conversation.current_state:
            menu_text = self.template_service.get_main_menu()

            conversation.current_state = "awaiting_category_selection"
            conversation.current_category = None
            conversation.current_intent = ""
            conversation.last_bot_prompt = menu_text
            conversation.save(update_fields=[
                "current_state",
                "current_category",
                "current_intent",
                "last_bot_prompt",
                "updated_at",
            ])

            return {
                "action": "reply_only",
                "reply_text": menu_text,
                "buttons": self.template_service.get_main_menu_buttons(),
            }

        if conversation.current_state == "awaiting_category_selection":
            category = self.detect_category(user_text)

            if not category:
                return {
                    "action": "reply_only",
                    "reply_text": self.template_service.get_invalid_menu(),
                    "buttons": self.template_service.get_main_menu_buttons(),
                }

            template_text = self.template_service.get_template(category)

            conversation.current_category = category
            conversation.current_intent = category.code
            conversation.current_state = "awaiting_form"
            conversation.state_entered_at = timezone.now()
            conversation.last_bot_prompt = template_text
            conversation.form_retry_count = 0
            conversation.save(update_fields=[
                "current_category",
                "current_intent",
                "current_state",
                "state_entered_at",
                "last_bot_prompt",
                "form_retry_count",
                "updated_at",
            ])

            return {
                "action": "reply_only",
                "reply_text": template_text,
            }

        if conversation.current_state == "awaiting_form":
            category = conversation.current_category
            if not category and conversation.current_intent:
                category = IntakeCategory.objects.filter(code=conversation.current_intent, is_active=True).first()

            if not category:
                return self._reset_to_menu(conversation)

            if self._is_cancel_command(user_text):
                return self._reset_to_menu(conversation)

            from social_messages.models import Message
            messages = Message.objects.filter(
                conversation=conversation,
                sent_at__gte=conversation.state_entered_at or conversation.updated_at
            ).order_by("sent_at")

            accumulated_parts = []
            for m in messages:
                content = (m.content or "").strip()
                if content and not self._is_cancel_command(content) and not self._is_finish_command(content):
                    accumulated_parts.append(content)

            accumulated_text = "\n".join(accumulated_parts)

            result = self.intake_filter.validate(category, accumulated_text)
            is_finish = self._is_finish_command(user_text)

            if result.is_valid or (is_finish and result.is_valid):
                return {
                    "action": "save_and_process",
                    "category_id": category.id,
                    "intent": category.code,
                    "cleaned_data": result.cleaned_data,
                }

            if is_finish:
                conversation.form_retry_count += 1

                if conversation.form_retry_count >= 3:
                    menu_text = self.template_service.get_main_menu()

                    conversation.current_state = "awaiting_category_selection"
                    conversation.current_category = None
                    conversation.current_intent = ""
                    conversation.state_entered_at = None
                    conversation.last_bot_prompt = menu_text
                    conversation.form_retry_count = 0
                    conversation.save(update_fields=[
                        "current_state",
                        "current_category",
                        "current_intent",
                        "state_entered_at",
                        "last_bot_prompt",
                        "form_retry_count",
                        "updated_at",
                    ])

                    return {
                        "action": "reply_only",
                        "reply_text": (
                            "Anh/chị đã nhập sai mẫu quá 3 lần. "
                            "Hệ thống sẽ đưa anh/chị quay lại menu chính.\n\n"
                            f"{menu_text}"
                        ),
                        "buttons": self.template_service.get_main_menu_buttons(),
                    }

                conversation.save(update_fields=["form_retry_count", "updated_at"])

                missing = ", ".join(result.missing_fields) if result.missing_fields else "không xác định"
                template_text = self.template_service.get_template(category)

                return {
                    "action": "reply_only",
                    "reply_text": (
                        "Nội dung chưa đúng mẫu hoặc còn thiếu thông tin bắt buộc.\n"
                        f"Các mục còn thiếu/chưa hợp lệ: {missing}\n\n"
                        f"{template_text}"
                    ),
                    "buttons": [
                        {"title": "Hoàn tất khai báo", "type": "oa.query.show", "payload": "Xong"},
                        {"title": "Hủy khai báo", "type": "oa.query.show", "payload": "Huỷ"}
                    ],
                }

            return {
                "action": "reply_only",
                "reply_text": "Hệ thống đã nhận thông tin. Anh/chị có thể tiếp tục gửi thêm, hoặc nhấn 'Hoàn tất khai báo' nếu đã xong, 'Hủy khai báo' để quay lại.",
                "buttons": [
                    {"title": "Hoàn tất khai báo", "type": "oa.query.show", "payload": "Xong"},
                    {"title": "Hủy khai báo", "type": "oa.query.show", "payload": "Huỷ"}
                ],
            }

        return self._reset_to_menu(conversation)

    def _reset_to_menu(self, conversation):
        menu_text = self.template_service.get_main_menu()

        conversation.current_state = "awaiting_category_selection"
        conversation.current_category = None
        conversation.current_intent = ""
        conversation.state_entered_at = None
        conversation.last_bot_prompt = menu_text
        conversation.form_retry_count = 0
        conversation.save(update_fields=[
            "current_state",
            "current_category",
            "current_intent",
            "state_entered_at",
            "last_bot_prompt",
            "form_retry_count",
            "updated_at",
        ])

        return {
            "action": "reply_only",
            "reply_text": menu_text,
            "buttons": self.template_service.get_main_menu_buttons(),
        }

    def _normalize(self, value: str) -> str:
        value = str(value or "").strip().lower()
        value = unicodedata.normalize("NFD", value)
        value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
        value = re.sub(r"[^a-z0-9\s_\-]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _is_cancel_command(self, text: str) -> bool:
        normalized = self._normalize(text)
        return normalized in ["huy", "huy bo", "quay lai"]

    def _is_finish_command(self, text: str) -> bool:
        normalized = self._normalize(text)
        return normalized in ["xong", "Xong", "hoan tat", "Hoan tat"]

