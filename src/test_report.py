import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from social_messages.tasks import send_daily_24h_summary_report

def run_test():
    result = send_daily_24h_summary_report()
    print("Test Result:", result)

if __name__ == '__main__':
    run_test()
