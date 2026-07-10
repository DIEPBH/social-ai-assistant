import json
import os
from typing import Any, Dict

from .gemini_analyzer import GeminiAnalyzer


class AIAnalysisService:
    def __init__(self) -> None:
        self.engine = os.getenv("AI_ENGINE", "stub")

    def analyze_message(self, content: Any) -> Dict[str, Any]:
        normalized_content = self._normalize_input(content)

        if self.engine in ["stub", "gemini"]:
            analyzer = GeminiAnalyzer()
            result = analyzer.analyze_message(normalized_content)
            result["selected_engine"] = self.engine
            return result

        analyzer = GeminiAnalyzer()
        result = analyzer.analyze_message(normalized_content)
        result["selected_engine"] = "default_fallback"
        return result

    def _normalize_input(self, content: Any) -> str:
        if isinstance(content, dict):
            return json.dumps(content, ensure_ascii=False)
        if isinstance(content, list):
            return json.dumps(content, ensure_ascii=False)
        return str(content or "")