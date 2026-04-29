from typing import Any, Dict

from django.conf import settings

from social_messages.services.zalo_sender import ZaloOASender

import requests


class OutboundMessageService:
    def send_text(self, conversation, text: str):
        platform = conversation.channel.platform

        if platform == "zalo":
            return self._send_zalo_text(conversation, text)

        if platform == "facebook":
            return self._send_facebook_text(conversation, text)

        return {
            "status": "error",
            "reason": f"unsupported_platform_{platform}",
        }

    def _send_zalo_text(self, conversation, text: str) -> Dict[str, Any]:
        access_token = conversation.channel.access_token or getattr(settings, "ZALO_OA_ACCESS_TOKEN", "")
        user_id = conversation.customer_id

        sender = ZaloOASender()
        result = sender.send_text_message(
            access_token=access_token,
            user_id=user_id,
            text=text,
        )

        return {
            "status": "success",
            "provider": "zalo",
            "result": result,
        }

    def _send_facebook_text(self, conversation, text: str) -> Dict[str, Any]:
        page_access_token = conversation.channel.access_token or getattr(settings, "FACEBOOK_PAGE_ACCESS_TOKEN", "")
        psid = conversation.customer_id

        if not page_access_token:
            return {
                "status": "error",
                "reason": "missing_facebook_page_access_token",
            }

        url = "https://graph.facebook.com/v23.0/me/messages"
        params = {
            "access_token": page_access_token,
        }
        payload = {
            "recipient": {"id": psid},
            "message": {"text": text},
        }

        response = requests.post(url, params=params, json=payload, timeout=20)

        return {
            "status": "success" if response.ok else "error",
            "provider": "facebook",
            "status_code": response.status_code,
            "body": response.text,
        }
    # outbound_message_service.py
    def send_text_with_buttons(self, conversation, text, buttons):
        if conversation.channel.platform == "zalo":
            sender = ZaloOASender()
            return sender.send_text_message_with_buttons(
                access_token=conversation.channel.access_token,
                user_id=conversation.customer_id,
                text=text,
                buttons=buttons,
            )

        return self.send_text(conversation, text)