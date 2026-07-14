import json
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from social_messages.models import Channel, CustomerBlacklist
from webhooks.views import handle_incoming
from django.core.cache import cache

# Clear cache for the test
cache.clear()
CustomerBlacklist.objects.all().delete()

Channel.objects.get_or_create(
    external_id="test_zalo_channel",
    defaults={
        "name": "Test Zalo Channel",
        "platform": "zalo",
        "is_active": True
    }
)

payload = {
    "platform": "zalo",
    "channel_external_id": "test_zalo_channel",
    "customer_id": "test_spammer_123",
    "platform_message_id": "msg_001",
    "sender_id": "test_spammer_123",
    "sender_type": "customer",
    "content": "Hello, this is spam"
}

print("Testing rate limit...")
for i in range(12):
    payload["platform_message_id"] = f"msg_{i}"
    try:
        res = handle_incoming(payload)
        print(f"Message {i+1}: status={res.get('status')}, reason={res.get('reason')}")
    except Exception as e:
        print(f"Message {i+1} Exception: {e}")

print("\nTesting Blacklist...")
CustomerBlacklist.objects.create(
    customer_id="test_blacklisted_123",
    is_active=True
)

payload["customer_id"] = "test_blacklisted_123"
payload["sender_id"] = "test_blacklisted_123"

# First time sending, should get blacklisted response
payload["platform_message_id"] = "msg_bl_1"
try:
    res = handle_incoming(payload)
    print(f"Blacklist msg 1: status={res.get('status')}, reason={res.get('reason')}")
except Exception as e:
    print(f"Blacklist msg 1 Exception: {e}")

# Second time sending, should still be blacklisted but debounce triggered (silently ignored)
payload["platform_message_id"] = "msg_bl_2"
try:
    res = handle_incoming(payload)
    print(f"Blacklist msg 2: status={res.get('status')}, reason={res.get('reason')}")
except Exception as e:
    print(f"Blacklist msg 2 Exception: {e}")
