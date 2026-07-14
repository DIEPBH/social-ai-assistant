import requests
import json
import time
import os
import django

# Setup django to access models if needed
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from social_messages.models import Channel, CustomerBlacklist

# Create test channel if not exists
Channel.objects.get_or_create(
    external_id="test_zalo_channel",
    defaults={
        "name": "Test Zalo Channel",
        "platform": "zalo",
        "is_active": True
    }
)

url = "http://localhost:8000/webhooks/test-message/"
headers = {"Content-Type": "application/json"}

payload = {
    "platform": "zalo",
    "channel_external_id": "test_zalo_channel",
    "customer_id": "test_spammer_123",
    "platform_message_id": "msg_001",
    "sender_id": "test_spammer_123",
    "sender_type": "customer",
    "content": "Hello, this is spam"
}

# 1. Test rate limit
print("Testing rate limit...")
for i in range(12):
    payload["platform_message_id"] = f"msg_{i}"
    response = requests.post(url, headers=headers, json=payload)
    try:
        res_json = response.json()
        print(f"Message {i+1}: status={res_json.get('status')}, reason={res_json.get('reason')}")
    except Exception as e:
        print(f"Message {i+1}: {response.status_code} {response.text}")
    time.sleep(0.1)

# 2. Test blacklist
print("\nTesting Blacklist...")
CustomerBlacklist.objects.get_or_create(
    customer_id="test_blacklisted_123",
    defaults={"is_active": True}
)

payload["customer_id"] = "test_blacklisted_123"
payload["sender_id"] = "test_blacklisted_123"
payload["platform_message_id"] = "msg_bl_1"

# First time sending, should get blacklisted response
response = requests.post(url, headers=headers, json=payload)
try:
    res_json = response.json()
    print(f"Blacklist msg 1: status={res_json.get('status')}, reason={res_json.get('reason')}")
except Exception as e:
    print(f"Blacklist msg 1: {response.status_code} {response.text}")

# Second time sending, should still be blacklisted but debounce triggered (silently ignored)
payload["platform_message_id"] = "msg_bl_2"
response = requests.post(url, headers=headers, json=payload)
try:
    res_json = response.json()
    print(f"Blacklist msg 2: status={res_json.get('status')}, reason={res_json.get('reason')}")
except Exception as e:
    print(f"Blacklist msg 2: {response.status_code} {response.text}")

