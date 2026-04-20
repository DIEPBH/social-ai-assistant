from django.urls import path
from .views import (
    health_check,
    test_message_webhook,
    facebook_webhook,
    zalo_webhook,
    zalo_oauth_callback,
)

urlpatterns = [
    path("health/", health_check, name="webhooks-health"),
    path("test-message/", test_message_webhook, name="test-message-webhook"),
    path("facebook/", facebook_webhook, name="facebook_webhook"),
    path("zalo/", zalo_webhook, name="zalo_webhook"),
    path("", health_check, name="webhooks-root-health"),  # Đảm bảo rằng URL gốc cũng được định tuyến đến health_check
    path("zalo/oauth/callback/", zalo_oauth_callback, name="zalo_oauth_callback"),
]