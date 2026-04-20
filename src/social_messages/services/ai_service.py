import os
from typing import Any, Dict

from .openclaw_analyzer import OpenClawAnalyzer


class AIAnalysisService:
    """
    Service trung gian để tách Celery task ra khỏi AI engine cụ thể.
    """

    def __init__(self) -> None:
        self.engine = os.getenv("AI_ENGINE", "stub")

    def analyze_message(self, content: str) -> Dict[str, Any]:
        if self.engine in ["stub", "openclaw_service"]:
            analyzer = OpenClawAnalyzer()
            result = analyzer.analyze_message(content)
            result["selected_engine"] = self.engine
            return result

        analyzer = OpenClawAnalyzer()
        result = analyzer.analyze_message(content)
        result["selected_engine"] = "default_fallback"
        return result