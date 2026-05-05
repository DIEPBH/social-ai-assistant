import logging

from social_messages.services.outbound_message_service import OutboundMessageService

logger = logging.getLogger(__name__)


class AdminReplyService:
    def send(self, message, text: str):
        try:
            service = OutboundMessageService()
            return service.send_text(message.conversation, text)
        except Exception as exc:
            logger.exception(
                "AdminReplyService failed message_id=%s",
                getattr(message, "id", None),
            )
            return {
                "status": "error",
                "error": str(exc),
            }