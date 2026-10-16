import json
import os
from typing import Any, Dict, Optional

from .gemini_analyzer import GeminiAnalyzer


class AIAnalysisService:
    def __init__(self) -> None:
        self.engine = os.getenv("AI_ENGINE", "stub")

    def analyze_message(self, content: Any, session_id: Optional[str] = None) -> Dict[str, Any]:
        normalized_content = self._normalize_input(content)

        analyzer = GeminiAnalyzer()
        result = analyzer.analyze_message(normalized_content, session_id=session_id)
        result["selected_engine"] = self.engine if self.engine in ["stub", "gemini"] else "default_fallback"
        return result

    def _normalize_input(self, content: Any) -> str:
        if isinstance(content, dict):
            return json.dumps(content, ensure_ascii=False)
        if isinstance(content, list):
            return json.dumps(content, ensure_ascii=False)
        return str(content or "")