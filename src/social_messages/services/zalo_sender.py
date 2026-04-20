from typing import Any, Dict

import requests


class ZaloOASender:
    SEND_MESSAGE_URL = "https://openapi.zalo.me/v2.0/oa/message"

    def send_text_message(self, access_token: str, user_id: str, text: str) -> Dict[str, Any]:
        if not access_token:
            raise ValueError("Missing Zalo OA access token")

        if not user_id:
            raise ValueError("Missing Zalo user_id")

        headers = {
            "access_token": access_token,
            "Content-Type": "application/json",
        }

        payload = {
            "recipient": {
                "user_id": user_id,
            },
            "message": {
                "text": text,
            }
        }

        response = requests.post(
            self.SEND_MESSAGE_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
