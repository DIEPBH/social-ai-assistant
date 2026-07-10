import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from social_messages.services.gemini_analyzer import GeminiAnalyzer

def run_tests():
    analyzer = GeminiAnalyzer()
    
    msg1 = "Nhà tôi ở xã Tân Lập vừa bị trộm cạy cửa lấy mất 1 chiếc xe máy SH."
    msg2 = "Cho tôi hỏi thủ tục làm lại căn cước công dân bị mất cần mang theo những giấy tờ gì?"

    print("--- Test 1 ---")
    print(f"Message: {msg1}")
    try:
        res1 = analyzer.analyze_message(msg1)
        print(f"Parsed fields: {json.dumps(res1, ensure_ascii=False, indent=2)}")
        print("-> OK: Successfully connected to Gemini API and parsed!")
    except Exception as e:
        print(f"-> FAILED: Reason: {e}")

    print("\n--- Test 2 ---")
    print(f"Message: {msg2}")
    try:
        res2 = analyzer.analyze_message(msg2)
        print(f"Parsed fields: {json.dumps(res2, ensure_ascii=False, indent=2)}")
        print("-> OK: Successfully connected to Gemini API and parsed!")
    except Exception as e:
        print(f"-> FAILED: Reason: {e}")

if __name__ == "__main__":
    run_tests()
