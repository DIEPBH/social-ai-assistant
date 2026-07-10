from typing import Any, Dict, List

import requests


class ZaloOASender:
    SEND_MESSAGE_URL = "https://openapi.zalo.me/v2.0/oa/message"

    def send_text_message(self, access_token: str, user_id: str, text: str) -> Dict[str, Any]:
        return self.send_text_message_with_buttons(
            access_token=access_token,
            user_id=user_id,
            text=text,
            buttons=None,
        )

    def send_text_message_with_buttons(
        self,
        access_token: str,
        user_id: str,
        text: str,
        buttons: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        if not access_token:
            raise ValueError("Missing Zalo OA access token")

        if not user_id:
            raise ValueError("Missing Zalo user_id")

        headers = {
            "access_token": access_token,
            "Content-Type": "application/json",
        }

        message = {
            "text": text,
        }

        if buttons:
            message["attachment"] = {
                "type": "template",
                "payload": {
                    "buttons": buttons
                }
            }

        payload = {
            "recipient": {
                "user_id": user_id,
            },
            "message": message,
        }

        import time
        from social_messages.models import IntegrationLog
        
        start_time = time.time()
        error_msg = ""
        response = None
        try:
            response = requests.post(
                self.SEND_MESSAGE_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            processing_time_ms = (time.time() - start_time) * 1000
            resp_json = {}
            if response:
                try:
                    resp_json = response.json()
                except Exception:
                    resp_json = {"raw_text": response.text}
            
            IntegrationLog.objects.create(
                system="zalo_api",
                direction="outbound",
                endpoint=self.SEND_MESSAGE_URL,
                method="POST",
                status_code=response.status_code if response else None,
                request_payload=payload,
                response_payload=resp_json,
                error_message=error_msg,
                processing_time_ms=processing_time_ms
            )

        return resp_json