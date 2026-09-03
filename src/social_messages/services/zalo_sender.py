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

    def send_attachment(
        self,
        access_token: str,
        user_id: str,
        attachment: Dict[str, Any],
        caption: str = "",
    ) -> Dict[str, Any]:
        """
        Gửi tệp đính kèm (ảnh, video, tệp tin) qua Zalo OA.
        - Nếu là image: thử gửi bằng send_media_template_message.
        - Nếu là file/video/audio hoặc khi media template thất bại:
          thử tải tạm thời và dùng upload_file + send_file_message.
        - Nếu vẫn thất bại: gửi fallback tin nhắn văn bản kèm link xem/tải trực tiếp.
        """
        import os
        import tempfile
        from urllib.parse import urlparse
        import logging

        local_logger = logging.getLogger(__name__)

        att_type = attachment.get("type", "file")
        url = attachment.get("url") or ""
        name = attachment.get("name") or ("Tệp đính kèm" if att_type != "image" else "Hình ảnh đính kèm")

        if not url:
            return {"status": "error", "reason": "empty_url"}

        text_label = caption or f"📎 {name}"

        # 1. Nếu là hình ảnh:
        if att_type == "image":
            try:
                res = self.send_media_template_message(
                    access_token=access_token,
                    user_id=user_id,
                    text=text_label,
                    image_url=url,
                )
                if res.get("error") == 0 or not res.get("error"):
                    return {"status": "success", "method": "media_template", "result": res}
            except Exception as e:
                local_logger.warning("send_media_template_message failed for %s: %s", url, e)

        # 2. Thử tải file tạm thời và gửi qua API upload_file + send_file_message
        try:
            parsed = urlparse(url)
            ext = os.path.splitext(parsed.path)[1] or (".jpg" if att_type == "image" else ".dat")
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp_path = tmp.name

            resp = requests.get(url, timeout=20, stream=True)
            resp.raise_for_status()
            file_size = 0
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    file_size += len(chunk)

            # Giới hạn Zalo OA upload file thường là 5MB
            if file_size <= 5 * 1024 * 1024:
                file_token = self.upload_file(access_token, tmp_path)
                file_res = self.send_file_message(access_token, user_id, file_token)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                return {"status": "success", "method": "file_message", "result": file_res}
            else:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        except Exception as e:
            local_logger.warning("upload_file + send_file_message failed for %s: %s", url, e)
            try:
                if "tmp_path" in locals() and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

        # 3. Fallback: Gửi tin nhắn chứa link tải trực tiếp
        fallback_text = f"{text_label}\n🔗 Link xem/tải: {url}"
        fb_res = self.send_text_message(access_token=access_token, user_id=user_id, text=fallback_text)
        return {"status": "success", "method": "link_fallback", "result": fb_res}

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