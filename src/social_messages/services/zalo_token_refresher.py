import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class ZaloTokenRefresher:
    TOKEN_URL = "https://oauth.zaloapp.com/v4/oa/access_token"

    def refresh_channel_token(self, channel):
        if channel.platform != "zalo":
            return {
                "status": "ignored",
                "reason": "not_zalo_channel",
                "channel_id": channel.id,
            }

        if not channel.refresh_token:
            return {
                "status": "error",
                "reason": "missing_refresh_token",
                "channel_id": channel.id,
            }

        app_id = getattr(settings, "ZALO_APP_ID", "")
        app_secret = getattr(settings, "ZALO_APP_SECRET", "")

        if not app_id or not app_secret:
            return {
                "status": "error",
                "reason": "missing_zalo_app_config",
                "channel_id": channel.id,
            }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "secret_key": app_secret,
        }

        data = {
            "refresh_token": channel.refresh_token,
            "app_id": app_id,
            "grant_type": "refresh_token",
        }

        response = requests.post(
            self.TOKEN_URL,
            headers=headers,
            data=data,
            timeout=15,
        )

        try:
            payload = response.json()
        except ValueError:
            payload = {"raw_text": response.text}

        if response.status_code >= 400 or payload.get("error"):
            logger.error(
                "Zalo refresh token failed channel_id=%s status=%s payload=%s",
                channel.id,
                response.status_code,
                payload,
            )
            return {
                "status": "error",
                "reason": "zalo_api_error",
                "channel_id": channel.id,
                "http_status": response.status_code,
                "payload": payload,
            }

        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token") or channel.refresh_token
        expires_in = int(payload.get("expires_in") or 3600)

        if not access_token:
            return {
                "status": "error",
                "reason": "missing_access_token_in_response",
                "channel_id": channel.id,
                "payload": payload,
            }

        channel.access_token = access_token
        channel.refresh_token = refresh_token
        channel.access_token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        channel.token_last_refreshed_at = timezone.now()
        channel.save(update_fields=[
            "access_token",
            "refresh_token",
            "access_token_expires_at",
            "token_last_refreshed_at",
        ])

        logger.info(
            "Zalo token refreshed channel_id=%s expires_in=%s",
            channel.id,
            expires_in,
        )

        return {
            "status": "success",
            "channel_id": channel.id,
            "expires_in": expires_in,
            "access_token_expires_at": channel.access_token_expires_at.isoformat(),
        }

    def refresh_if_needed(self, channel, buffer_minutes=10):
        if channel.platform != "zalo":
            return {
                "status": "ignored",
                "reason": "not_zalo_channel",
                "channel_id": channel.id,
            }

        if not channel.access_token_expires_at:
            return self.refresh_channel_token(channel)

        refresh_before = timezone.now() + timedelta(minutes=buffer_minutes)

        if channel.access_token_expires_at <= refresh_before:
            return self.refresh_channel_token(channel)

        return {
            "status": "skipped",
            "reason": "token_still_valid",
            "channel_id": channel.id,
            "access_token_expires_at": channel.access_token_expires_at.isoformat(),
        }