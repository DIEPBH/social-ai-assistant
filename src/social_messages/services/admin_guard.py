from django.conf import settings
import logging
logger = logging.getLogger(__name__)

class AdminGuard:
    def is_zalo_admin(self, sender_id: str) -> bool:
        normalized = str(sender_id or "").strip()
        if not normalized:
            return False

        allowed_ids = {
            str(item).strip()
            for item in getattr(settings, "ZALO_ADMIN_SENDER_IDS", [])
            if str(item).strip()
        }
        
        return normalized in allowed_ids

    def is_admin_message(self, platform: str, sender_id: str) -> bool:
        if platform != "zalo":
            return False
        return self.is_zalo_admin(sender_id)