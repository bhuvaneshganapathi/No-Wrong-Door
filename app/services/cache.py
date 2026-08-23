"""
Thread-safe In-Memory TTL Cache
"""
import time
import threading
from typing import Any, Optional, Dict, Tuple
from app.config import CACHE_TTL_SECONDS

class TTLCache:
    def __init__(self, default_ttl: int = CACHE_TTL_SECONDS):
        self.default_ttl = default_ttl
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            self._store[key] = (value, expiry)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._store:
                return None
            value, expiry = self._store[key]
            if time.time() > expiry:
                del self._store[key]
                return None
            return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

# Global singleton cache instance
global_cache = TTLCache()
