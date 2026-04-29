from social_messages.services.intake_template_service import IntakeTemplateService
from social_messages.services.message_intake_filter import MessageIntakeFilter


class IntakeRouter:
    def __init__(self):
        self.template_service = IntakeTemplateService()
        self.intake_filter = MessageIntakeFilter()

    def detect_category(self, text: str):
        normalized = (text or "").strip().lower()

        if normalized == "1":
            return "complaint"
        if normalized == "2":
            return "crime_report"
        if normalized == "3":
            return "admin_procedure"

        return None

    def map_intent_to_state(self, intent: str):
        if intent in {"complaint", "crime_report", "admin_procedure"}:
            return "awaiting_form"
        return ""

    def route(self, conversation, user_text: str):
        if not conversation.current_state:
            menu_text = self.template_service.get_main_menu()

            conversation.current_state = "awaiting_category_selection"
            conversation.last_bot_prompt = menu_text
            conversation.save(update_fields=["current_state", "last_bot_prompt", "updated_at"])

            return {
                "action": "reply_only",
                "reply_text": menu_text,
            }

        if conversation.current_state == "awaiting_category_selection":
            intent = self.detect_category(user_text)

            if not intent:
                return {
                    "action": "reply_only",
                    "reply_text": self.template_service.get_invalid_menu(),
                }

            template_text = self.template_service.get_template(intent)

            conversation.current_intent = intent
            conversation.current_state = self.map_intent_to_state(intent)
            conversation.last_bot_prompt = template_text
            conversation.form_retry_count = 0
            conversation.save(update_fields=[
                "current_intent",
                "current_state",
                "last_bot_prompt",
                "form_retry_count",
                "updated_at",
            ])

            return {
                "action": "reply_only",
                "reply_text": template_text,
            }

        if conversation.current_state == "awaiting_form":
            result = self.intake_filter.validate(conversation.current_intent, user_text)

            if not result.is_valid:
                conversation.form_retry_count += 1

                if conversation.form_retry_count >= 3:
                    menu_text = self.template_service.get_main_menu()

                    conversation.current_state = "awaiting_category_selection"
                    conversation.current_intent = ""
                    conversation.last_bot_prompt = menu_text
                    conversation.form_retry_count = 0
                    conversation.save(update_fields=[
                        "current_state",
                        "current_intent",
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
                    }

                conversation.save(update_fields=["form_retry_count", "updated_at"])

                missing = ", ".join(result.missing_fields) if result.missing_fields else "không xác định"
                template_text = self.template_service.get_template(conversation.current_intent)

                return {
                    "action": "reply_only",
                    "reply_text": (
                        "Nội dung chưa đúng mẫu hoặc còn thiếu thông tin bắt buộc.\n"
                        f"Các mục còn thiếu: {missing}\n\n"
                        f"{template_text}"
                    ),
                }

            return {
                "action": "save_and_process",
                "intent": conversation.current_intent,
                "cleaned_data": result.cleaned_data,
            }

        menu_text = self.template_service.get_main_menu()

        conversation.current_state = "awaiting_category_selection"
        conversation.current_intent = ""
        conversation.last_bot_prompt = menu_text
        conversation.form_retry_count = 0
        conversation.save(update_fields=[
            "current_state",
            "current_intent",
            "last_bot_prompt",
            "form_retry_count",
            "updated_at",
        ])

        return {
            "action": "reply_only",
            "reply_text": menu_text,
        }