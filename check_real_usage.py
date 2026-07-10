import os
import re

models = [
    "Channel", "IntakeCategory", "IntakeTemplate", "IntakeTemplateField",
    "IntakeValidationRule", "KeywordRule", "AdminCommand", "AdminCommandPattern",
    "Conversation", "Message", "MessageAnalysis", "Report", "IntakeSubmission",
    "IntegrationLog"
]

counts = {m: 0 for m in models}

for root, _, files in os.walk("src"):
    for file in files:
        if file.endswith(".py") and file not in ["models.py", "admin.py"]:
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                for m in models:
                    matches = len(re.findall(r'\b' + m + r'\b', content))
                    counts[m] += matches
                    if matches > 0:
                        print(f"Model {m} used in {path} ({matches} times)")

print("\nSummary (Excluding models.py & admin.py):")
for m, c in counts.items():
    if c == 0:
        print(f"  {m}: UNUSED")
    else:
        print(f"  {m}: {c} usages")
