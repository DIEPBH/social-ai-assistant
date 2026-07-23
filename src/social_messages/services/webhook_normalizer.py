
from typing import Any, Dict, Optional
from social_messages.services.admin_guard import AdminGuard
import logging
logger = logging.getLogger(__name__)


class WebhookNormalizer:
    def normalize_zalo_message(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Chuẩn hóa payload Zalo về schema nội bộ.
        Tạm thời xử lý theo hướng an toàn:
        - cố lấy các field phổ biến
        - nếu thiếu dữ liệu thì trả None để debug payload trước
        """
        message = payload.get("message") or {}
        sender = payload.get("sender") or {}
        recipient = payload.get("recipient") or {}
        sender_id = sender.get("id") or payload.get("user_id") or payload.get("fromuid")
        text = message.get("text") or payload.get("text") or ""
        msg_id = message.get("msg_id") or payload.get("msg_id") or payload.get("message_id")
        user_id = sender.get("id") or payload.get("user_id") or payload.get("fromuid")
        oa_id = recipient.get("id") or payload.get("oa_id")
        
        sender_type = "admin" if AdminGuard().is_zalo_admin(sender_id) else "customer"
        logger.warning("Zalo message_id: %s, sender_id: %s, sender_type: %s", msg_id, sender_id, sender_type)
        if not msg_id or not user_id:
            return None

        message_type = "text"
        event_name = payload.get("event_name", "")
        if event_name == "user_send_image":
            message_type = "image"
        elif event_name == "user_send_video":
            message_type = "video"
        elif event_name == "user_send_file":
            message_type = "file"
        elif event_name == "user_send_audio":
            message_type = "audio"

        raw_attachments = message.get("attachments", [])
        normalized_attachments = []
        for att in raw_attachments:
            att_type = att.get("type")
            att_payload = att.get("payload", {})
            normalized_attachments.append({
                "type": att_type,
                "url": att_payload.get("url"),
                "thumbnail": att_payload.get("thumbnail"),
            })
            if message_type == "text" and att_type in ["image", "video", "file", "audio"]:
                message_type = att_type

        return {
            "platform": "zalo",
            "channel_external_id": str(oa_id or "zalo_oa_main"),
            "customer_id": str(user_id),
            "customer_name": payload.get("display_name") or payload.get("user_name"),
            "platform_message_id": str(msg_id),
            "sender_type": sender_type,
            "message_type": message_type,
            "content": text,
            "raw_payload": payload,
            "sender_id": str(sender_id),
            "attachments": normalized_attachments,
        }

    def normalize_facebook_message(self, payload: Dict[str, Any]) -> list[Dict[str, Any]]:
        """
        Chuẩn hóa payload Meta Messenger webhook.
        Meta gửi object=page, entry[], messaging[].
        """
        normalized_messages = []

        if payload.get("object") != "page":
            return normalized_messages

        for entry in payload.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender = messaging_event.get("sender") or {}
                recipient = messaging_event.get("recipient") or {}
                message = messaging_event.get("message") or {}

                message_id = message.get("mid")
                sender_id = sender.get("id")
                recipient_id = recipient.get("id")
                text = message.get("text", "")

                if not message_id or not sender_id:
                    continue

                normalized_messages.append({
                    "platform": "facebook",
                    "channel_external_id": str(recipient_id or "facebook_page_main"),
                    "customer_id": str(sender_id),
                    "customer_name": None,
                    "platform_message_id": str(message_id),
                    "sender_id": str(sender_id),
                    "sender_type": "customer",
                    "message_type": "text",
                    "content": text,
                    "raw_payload": messaging_event,
                })

        return normalized_messages
