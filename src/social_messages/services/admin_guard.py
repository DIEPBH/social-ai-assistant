from django.conf import settings
import logging
from social_messages.models import UserProfile

logger = logging.getLogger(__name__)

class AdminGuard:
    def is_zalo_admin(self, sender_id: str) -> bool:
        normalized = str(sender_id or "").strip()
        if not normalized:
            return False

        # Check if an active user profile exists with this Zalo ID
        return UserProfile.objects.filter(zalo_id=normalized, user__is_active=True).exists()

    def is_admin_message(self, platform: str, sender_id: str) -> bool:
        if platform != "zalo":
            return False
        return self.is_zalo_admin(sender_id)