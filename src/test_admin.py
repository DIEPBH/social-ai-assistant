import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['ZALO_ADMIN_SENDER_IDS'] = 'admin_001'
django.setup()

from social_messages.models import Channel, Conversation, Message
from social_messages.tasks import process_admin_command

def run_test():
    channel, _ = Channel.objects.get_or_create(
        platform='zalo',
        defaults={'name': 'Zalo Test', 'is_active': True}
    )

    conv, _ = Conversation.objects.get_or_create(
        channel=channel,
        customer_id='admin_001'
    )

    import uuid
    from django.utils import timezone
    msg = Message.objects.create(
        conversation=conv,
        sender_id='admin_001',
        sender_type='user',
        platform_message_id=str(uuid.uuid4()),
        content='Tạo báo cáo tổng hợp từ ngày 1/7/2026 đến 10/7/2026',
        sent_at=timezone.now()
    )

    print(f"Created message ID: {msg.id}")

    try:
        result = process_admin_command(msg.id)
        print("Test Result:", result)
    except Exception as e:
        print("Error during process_admin_command:", e)

if __name__ == '__main__':
    run_test()
