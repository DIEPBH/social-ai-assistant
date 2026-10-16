import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import redis

logger = logging.getLogger(__name__)

CACHE_KEY_RULES = "pii_masking_rules_cache_v1"
CACHE_TTL_RULES = 3600  # 1 hour
TOKEN_MAP_TTL = 600  # 10 minutes, per user requirement


class PIIMaskingService:
    """
    Dịch vụ ẩn danh hóa dữ liệu cá nhân (PII Masking & Tokenization)
    Tuân thủ quy định tại Điều 25 Nghị định 13/2023/NĐ-CP khi sử dụng Cloud AI.
    """

    _redis_client = None

    @classmethod
    def get_redis_client(cls):
        if cls._redis_client is None:
            redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
            cls._redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        return cls._redis_client

    @classmethod
    def invalidate_cache(cls) -> None:
        """Xóa cache rules trong Redis khi có cập nhật trong Django Admin."""
        try:
            r = cls.get_redis_client()
            r.delete(CACHE_KEY_RULES)
            logger.info("PIIMaskingService: Cleared rules cache in Redis")
        except Exception as e:
            logger.warning(f"PIIMaskingService: Failed to invalidate Redis cache: {e}")

    @classmethod
    def get_active_rules(cls) -> List[Dict[str, Any]]:
        """Lấy danh sách các rule đang kích hoạt (ưu tiên từ Redis Cache)."""
        r = None
        try:
            r = cls.get_redis_client()
            cached_data = r.get(CACHE_KEY_RULES)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"PIIMaskingService: Redis read error for rules: {e}")

        # Fallback to Database
        try:
            from social_messages.models import PIIMaskingRule
            rules_qs = PIIMaskingRule.objects.filter(is_active=True).order_by("priority", "id")
            rules = [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "rule_type": rule.rule_type,
                    "pattern": rule.pattern,
                    "token_prefix": rule.token_prefix,
                    "priority": rule.priority,
                }
                for rule in rules_qs
            ]
            if r:
                try:
                    r.setex(CACHE_KEY_RULES, CACHE_TTL_RULES, json.dumps(rules, ensure_ascii=False))
                except Exception as e:
                    logger.warning(f"PIIMaskingService: Redis write error for rules: {e}")
            return rules
        except Exception as e:
            logger.error(f"PIIMaskingService: Failed to query PIIMaskingRule from DB: {e}")
            return []

    @classmethod
    def mask_pii(cls, text: str, session_id: Optional[str] = None) -> Tuple[str, Dict[str, str]]:
        """
        Quét và thay thế các trường PII nhạy cảm (CCCD, SĐT, Tên, Địa chỉ...) thành Token.
        Trả về: (masked_text, token_to_raw_map)
        Lưu mapping vào Redis với TTL 10 phút nếu có session_id.
        """
        if not text or not isinstance(text, str):
            return text or "", {}

        rules = cls.get_active_rules()
        if not rules:
            return text, {}

        masked_text = text
        token_to_raw: Dict[str, str] = {}
        prefix_counters: Dict[str, int] = {}

        for rule in rules:
            rule_type = rule.get("rule_type", "regex")
            pattern_str = rule.get("pattern", "")
            prefix = rule.get("token_prefix", "PII")

            if not pattern_str:
                continue

            try:
                if rule_type == "regex":
                    compiled_regex = re.compile(pattern_str)
                    
                    # Tìm tất cả matches
                    matches = list(compiled_regex.finditer(masked_text))
                    if not matches:
                        continue

                    # Thay thế từ cuối chuỗi lên đầu để không làm lệch index
                    for match in reversed(matches):
                        # Nếu regex có capture group 1 (ví dụ group họ tên sau xưng danh), ưu tiên group 1
                        if match.groups() and match.group(1):
                            raw_val = match.group(1)
                            start_idx, end_idx = match.start(1), match.end(1)
                        else:
                            raw_val = match.group(0)
                            start_idx, end_idx = match.start(), match.end()

                        # Tránh mask lại nếu vị trí đã là Token
                        if "{{" in raw_val and "}}" in raw_val:
                            continue

                        # Tăng bộ đếm cho prefix
                        current_count = prefix_counters.get(prefix, 0) + 1
                        prefix_counters[prefix] = current_count
                        token = f"{{{{{prefix}_#{current_count}}}}}"

                        # Lưu ánh xạ Token -> Dữ liệu thật
                        token_to_raw[token] = raw_val

                        # Thay thế trong văn bản
                        masked_text = masked_text[:start_idx] + token + masked_text[end_idx:]

                elif rule_type == "keyword":
                    # Xử lý dạng từ khóa cố định
                    pattern_re = re.compile(re.escape(pattern_str), re.IGNORECASE)
                    matches = list(pattern_re.finditer(masked_text))
                    for match in reversed(matches):
                        raw_val = match.group(0)
                        if "{{" in raw_val and "}}" in raw_val:
                            continue
                        current_count = prefix_counters.get(prefix, 0) + 1
                        prefix_counters[prefix] = current_count
                        token = f"{{{{{prefix}_#{current_count}}}}}"
                        token_to_raw[token] = raw_val
                        masked_text = masked_text[:match.start()] + token + masked_text[match.end():]

            except Exception as e:
                logger.error(f"PIIMaskingService: Error applying rule '{rule.get('name')}': {e}")

        # Lưu token map vào Redis nếu có session_id
        if session_id and token_to_raw:
            try:
                r = cls.get_redis_client()
                redis_key = f"pii_token_map:{session_id}"
                # Lấy map cũ (nếu có) để merge
                existing_map = r.get(redis_key)
                combined_map = json.loads(existing_map) if existing_map else {}
                combined_map.update(token_to_raw)
                r.setex(redis_key, TOKEN_MAP_TTL, json.dumps(combined_map, ensure_ascii=False))
            except Exception as e:
                logger.warning(f"PIIMaskingService: Failed to save token map to Redis for {session_id}: {e}")

        return masked_text, token_to_raw

    @classmethod
    def demask_data(
        cls,
        data: Any,
        session_id: Optional[str] = None,
        mapping: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Giải mã dữ liệu đã bị che mờ bằng cách thay thế Token ngược về Dữ liệu thật.
        Hỗ trợ giải mã đệ quy cho string, dict, list.
        """
        combined_mapping: Dict[str, str] = {}
        if mapping:
            combined_mapping.update(mapping)

        if session_id:
            try:
                r = cls.get_redis_client()
                redis_key = f"pii_token_map:{session_id}"
                cached_map = r.get(redis_key)
                if cached_map:
                    redis_dict = json.loads(cached_map)
                    # Mapping truyền vào ưu tiên hơn hoặc bổ sung
                    redis_dict.update(combined_mapping)
                    combined_mapping = redis_dict
            except Exception as e:
                logger.warning(f"PIIMaskingService: Failed to read token map from Redis for {session_id}: {e}")

        if not combined_mapping:
            return data

        return cls._recursive_demask(data, combined_mapping)

    @classmethod
    def _recursive_demask(cls, item: Any, mapping: Dict[str, str]) -> Any:
        if isinstance(item, str):
            res = item
            for token, raw_val in mapping.items():
                if token in res:
                    res = res.replace(token, raw_val)
            return res
        elif isinstance(item, dict):
            return {k: cls._recursive_demask(v, mapping) for k, v in item.items()}
        elif isinstance(item, list):
            return [cls._recursive_demask(x, mapping) for x in item]
        return item
