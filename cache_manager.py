"""Performans optimizasyonu - JSON cache ve yardimci fonksiyonlar.

Bu modul sayesinde JSON dosya okumalari her seferinde disk'ten
yapilmaz, memory'de tutulan cache kullanilir.
"""
import os
import json
import time
import hashlib
import logging
from typing import Any, Optional, Callable
from functools import lru_cache, wraps

log = logging.getLogger("smmm.cache")

# Global cache - her dosya icin (path, mtime) -> data
_FILE_CACHE = {}
_FILE_CACHE_TIMES = {}
_DEFAULT_TTL = 60  # saniye


def cached_dosya_oku(path: str, default=None, ttl: int = _DEFAULT_TTL):
    """Dosya okuma - memory cache'li. Dosya degismisse veya TTL dolduysa tekrar okur."""
    if not path or not os.path.exists(path):
        return default

    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return default

    cache_key = path
    now = time.time()

    if cache_key in _FILE_CACHE:
        cached_mtime = _FILE_CACHE_TIMES.get(cache_key, 0)
        cached_time = _FILE_CACHE.get(f"{cache_key}._time", 0)
        if cached_mtime == mtime and (now - cached_time) < ttl:
            return _FILE_CACHE[cache_key]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _FILE_CACHE[cache_key] = data
        _FILE_CACHE_TIMES[cache_key] = mtime
        _FILE_CACHE[f"{cache_key}._time"] = now
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Cache okuma hatasi %s: %s", path, e)
        return default


def invalidate_cache(path: Optional[str] = None):
    """Cache'i temizle. path verilirse sadece o dosya, yoksa tum cache."""
    if path:
        keys_to_remove = [k for k in _FILE_CACHE if k == path or k.startswith(f"{path}._")]
        for k in keys_to_remove:
            _FILE_CACHE.pop(k, None)
            _FILE_CACHE_TIMES.pop(k, None)
    else:
        _FILE_CACHE.clear()
        _FILE_CACHE_TIMES.clear()


def cache_stats() -> dict:
    """Cache istatistikleri."""
    return {
        "cached_files": len([k for k in _FILE_CACHE if not k.endswith("._time")]),
        "total_entries": len(_FILE_CACHE),
    }


def hash_image(image_bytes: bytes) -> str:
    """Gorsel icin hizli hash hesapla (cache key olarak kullanilir)."""
    return hashlib.md5(image_bytes).hexdigest()


def timed(func: Callable) -> Callable:
    """Fonksiyonun calisma suresini logla."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            if elapsed > 100:  # 100ms'den uzun surerse logla
                log.debug("%s %.1fms surdu", func.__name__, elapsed)
    return wrapper
