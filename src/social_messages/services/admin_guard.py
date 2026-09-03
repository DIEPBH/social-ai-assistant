import logging
from typing import Optional
from django.contrib.auth.models import User
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

    def get_user_by_zalo_id(self, sender_id: str) -> Optional[User]:
        normalized = str(sender_id or "").strip()
        if not normalized:
            return None
        profile = UserProfile.objects.select_related("user").filter(
            zalo_id=normalized,
            user__is_active=True,
        ).first()
        return profile.user if profile else None

    def is_admin_user(self, user: Optional[User]) -> bool:
        if not user or not user.is_active:
            return False
        return user.is_superuser or user.groups.filter(name="Quản trị viên").exists()

    def is_specialist_user(self, user: Optional[User]) -> bool:
        if not user or not user.is_active:
            return False
        return user.groups.filter(name="Chuyên viên").exists()

    def get_user_role(self, user: Optional[User]) -> str:
        if not user or not user.is_active:
            return "unauthorized"
        if self.is_admin_user(user):
            return "admin"
        if self.is_specialist_user(user):
            return "specialist"
        return "unauthorized"