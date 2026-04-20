from django.conf import settings


class AdminGuard:
    def is_zalo_admin(self, sender_id: str) -> bool:
        if not sender_id:
            return False

        return sender_id in settings.ZALO_ADMIN_SENDER_IDS
