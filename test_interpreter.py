import os
import django
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from social_messages.services.admin_ai_interpreter import AdminAIInterpreter

interpreter = AdminAIInterpreter()
print("Testing interpret()...")
try:
    result = interpreter.interpret("tổng quan hôm nay")
    print("Result:", result)
except Exception as e:
    print("Error:", e)
