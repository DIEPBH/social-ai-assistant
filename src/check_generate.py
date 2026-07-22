import os
import requests

api_key = os.getenv("GEMINI_API_KEY", "")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
response = requests.get(url)
models = response.json().get("models", [])
print("Models supporting generateContent:")
for m in models:
    if "generateContent" in m.get("supportedGenerationMethods", []):
        print(f"- {m['name']}")
