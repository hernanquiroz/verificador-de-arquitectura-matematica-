import hashlib
import json
import os
from typing import Any, Optional

class CacheManager:
    def __init__(self, cache_dir: str = ".streamlit_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _get_file_hash(self, file_bytes: bytes) -> str:
        return hashlib.md5(file_bytes).hexdigest()

    def _get_cache_key(self, file_hash: str, batch_number: int, batch_size: int) -> str:
        return f"{file_hash}_b{batch_number}_s{batch_size}"

    def get_cached_batch(self, file_bytes: bytes, batch_number: int, batch_size: int) -> Optional[Any]:
        file_hash = self._get_file_hash(file_bytes)
        cache_key = self._get_cache_key(file_hash, batch_number, batch_size)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def save_batch_to_cache(self, file_bytes: bytes, batch_number: int, batch_size: int, data: Any):
        file_hash = self._get_file_hash(file_bytes)
        cache_key = self._get_cache_key(file_hash, batch_number, batch_size)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
