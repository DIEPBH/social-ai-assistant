import os
import re
from collections import defaultdict

models = [
    "Channel", "IntakeCategory", "IntakeTemplate", "IntakeTemplateField",
    "IntakeValidationRule", "KeywordRule", "AdminCommand", "AdminCommandPattern",
    "Conversation", "Message", "MessageAnalysis", "Report", "IntakeSubmission",
    "IntegrationLog"
]

counts = {m: 0 for m in models}

for root, _, files in os.walk("src"):
    for file in files:
        if file.endswith(".py") and file != "models.py":
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                for m in models:
                    counts[m] += len(re.findall(r'\b' + m + r'\b', content))

for m, c in counts.items():
    print(f"{m}: {c}")
