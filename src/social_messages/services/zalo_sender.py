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
        
        return self._send_payload(access_token, payload)

    def send_media_template_message(
        self,
        access_token: str,
        user_id: str,
        text: str,
        image_url: str
    ) -> Dict[str, Any]:
        if not access_token:
            raise ValueError("Missing Zalo OA access token")

        if not user_id:
            raise ValueError("Missing Zalo user_id")

        payload = {
            "recipient": {
                "user_id": user_id,
            },
            "message": {
                "text": text,
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "media",
                        "elements": [{
                            "media_type": "image",
                            "url": image_url
                        }]
                    }
                }
            },
        }

        return self._send_payload(access_token, payload)

    def send_list_template_message(
        self,
        access_token: str,
        user_id: str,
        elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not access_token:
            raise ValueError("Missing Zalo OA access token")

        if not user_id:
            raise ValueError("Missing Zalo user_id")

        payload = {
            "recipient": {
                "user_id": user_id,
            },
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "list",
                        "elements": elements
                    }
                }
            },
        }

        return self._send_payload(access_token, payload)

    def upload_file(self, access_token: str, file_path: str) -> str:
        url = "https://openapi.zalo.me/v2.0/oa/upload/file"
        headers = {
            "access_token": access_token
        }
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, headers=headers, files=files, timeout=60)
            response.raise_for_status()
            resp_json = response.json()
            if resp_json.get("error") != 0:
                raise ValueError(f"Failed to upload file to Zalo: {resp_json}")
            return resp_json["data"]["token"]

    def send_file_message(
        self,
        access_token: str,
        user_id: str,
        file_token: str
    ) -> Dict[str, Any]:
        if not access_token:
            raise ValueError("Missing Zalo OA access token")

        if not user_id:
            raise ValueError("Missing Zalo user_id")

        payload = {
            "recipient": {
                "user_id": user_id,
            },
            "message": {
                "attachment": {
                    "type": "file",
                    "payload": {
                        "token": file_token
                    }
                }
            },
        }

        return self._send_payload(access_token, payload)

    def get_user_profile(self, access_token: str, user_id: str) -> Dict[str, Any]:
        if not access_token:
            raise ValueError("Missing Zalo OA access token")
        if not user_id:
            raise ValueError("Missing Zalo user_id")

        url = "https://openapi.zalo.me/v2.0/oa/getprofile"
        headers = {
            "access_token": access_token
        }
        params = {
            "data": f'{{"user_id":"{user_id}"}}'
        }
        
        import time
        from social_messages.models import IntegrationLog
        
        start_time = time.time()
        error_msg = ""
        response = None
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
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
                endpoint=url,
                method="GET",
                status_code=response.status_code if response else None,
                request_payload=params,
                response_payload=resp_json,
                error_message=error_msg,
                processing_time_ms=processing_time_ms
            )

        return resp_json

    def _send_payload(self, access_token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "access_token": access_token,
            "Content-Type": "application/json",
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