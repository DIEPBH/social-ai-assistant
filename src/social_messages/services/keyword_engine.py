class KeywordEngine:
    def analyze_submission(self, submission):
        content = (submission.content or "").lower()
        intent = submission.intent

        if intent == "crime_report":
            urgent_keywords = [
                "vũ khí", "đe dọa", "đánh nhau", "cháy", "nổ",
                "bắt cóc", "khẩn cấp", "dao", "súng"
            ]

            if any(keyword in content for keyword in urgent_keywords):
                return {
                    "matched": True,
                    "engine": "keyword_engine",
                    "selected_engine": "keyword_engine",
                    "topic": "an ninh trật tự",
                    "sentiment": "tiêu cực",
                    "priority": "high",
                    "summary": submission.content,
                    "rule_name": "crime_urgent_v1",
                }

            if content:
                return {
                    "matched": True,
                    "engine": "keyword_engine",
                    "selected_engine": "keyword_engine",
                    "topic": "tin báo tội phạm",
                    "sentiment": "tiêu cực",
                    "priority": "normal",
                    "summary": submission.content,
                    "rule_name": "crime_general_v1",
                }

        if intent == "admin_procedure":
            if "hộ khẩu" in content or "cư trú" in content:
                return {
                    "matched": True,
                    "engine": "keyword_engine",
                    "selected_engine": "keyword_engine",
                    "topic": "thủ tục cư trú",
                    "sentiment": "trung lập",
                    "priority": "normal",
                    "summary": submission.content,
                    "rule_name": "procedure_residence_v1",
                }

            if "khai sinh" in content:
                return {
                    "matched": True,
                    "engine": "keyword_engine",
                    "selected_engine": "keyword_engine",
                    "topic": "hộ tịch khai sinh",
                    "sentiment": "trung lập",
                    "priority": "normal",
                    "summary": submission.content,
                    "rule_name": "procedure_birth_v1",
                }

        if intent == "complaint":
            urgent_keywords = ["khẩn cấp", "gấp", "nghiêm trọng", "ngay lập tức"]
            if any(keyword in content for keyword in urgent_keywords):
                return {
                    "matched": True,
                    "engine": "keyword_engine",
                    "selected_engine": "keyword_engine",
                    "topic": "khiếu nại khẩn cấp",
                    "sentiment": "tiêu cực",
                    "priority": "high",
                    "summary": submission.content,
                    "rule_name": "complaint_urgent_v1",
                }

            if any(keyword in content for keyword in ["khiếu nại", "phản ánh", "không giải quyết", "chậm xử lý"]):
                return {
                    "matched": True,
                    "engine": "keyword_engine",
                    "selected_engine": "keyword_engine",
                    "topic": "khiếu nại",
                    "sentiment": "tiêu cực",
                    "priority": "normal",
                    "summary": submission.content,
                    "rule_name": "complaint_general_v1",
                }

        return None