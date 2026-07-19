"""
Guvenlik modulu: rate limiting, input sanitization, XSS korumasi.
"""
import hashlib
import os
import re
import time
from collections import defaultdict
from functools import wraps
from typing import Optional


# ── Rate Limiter ──

class RateLimiter:
    """Basit bellek tabanli rate limiter (sliding window)."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str, now: float):
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        self._cleanup(key, now)
        if len(self._requests[key]) >= self.max_requests:
            return False
        self._requests[key].append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.time()
        self._cleanup(key, now)
        return max(0, self.max_requests - len(self._requests[key]))

    def reset(self, key: str):
        self._requests.pop(key, None)


# Global rate limiters
api_limiter = RateLimiter(max_requests=30, window_seconds=60)
login_limiter = RateLimiter(max_requests=5, window_seconds=300)
upload_limiter = RateLimiter(max_requests=10, window_seconds=60)


def rate_limit_check(limiter: RateLimiter, key: str) -> tuple[bool, int]:
    """Rate limit kontrolu. (allowed, remaining_kalan) dondurur."""
    allowed = limiter.is_allowed(key)
    remaining = limiter.remaining(key)
    return allowed, remaining


# ── Input Sanitization ──

# Zararli HTML/JS patternleri
_XSS_PATTERNS = [
    re.compile(r"<script\b", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"<iframe\b", re.IGNORECASE),
    re.compile(r"<object\b", re.IGNORECASE),
    re.compile(r"<embed\b", re.IGNORECASE),
    re.compile(r"<form\b", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
    re.compile(r"url\s*\(", re.IGNORECASE),
    re.compile(r"<link\b", re.IGNORECASE),
    re.compile(r"<meta\b", re.IGNORECASE),
    re.compile(r"<base\b", re.IGNORECASE),
]

# Tehlikeli karakterler (dosya yollarinda)
_PATH_DANGEROUS = re.compile(r"[\\/:*?\"<>|]")


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Kullanici girdisini temizle."""
    if not text:
        return ""
    text = text[:max_length]
    # Null byte temizle
    text = text.replace("\x00", "")
    # HTML taglarini temizle
    text = re.sub(r"<[^>]+>", "", text)
    # Script injection temizle
    for pat in _XSS_PATTERNS:
        text = pat.sub("", text)
    return text.strip()


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Dosya adini temizle."""
    if not filename:
        return "unnamed"
    # Tehlikeli karakterleri temizle
    filename = _PATH_DANGEROUS.sub("_", filename)
    # Path traversal onleme
    filename = filename.replace("..", "_")
    # Bossa default
    filename = filename.strip(" ._")
    if not filename:
        filename = "unnamed"
    return filename[:max_length]


def validate_vkn(vkn: str) -> bool:
    """Vergi numarasi dogrulama (10 haneli, algoritma)."""
    vkn = re.sub(r"[^\d]", "", str(vkn))
    if len(vkn) != 10:
        return False
    digits = [int(d) for d in vkn]
    total = (digits[0] + digits[1]) * 2
    for i in range(2, 10):
        total += digits[i] * (10 - i)
    remainder = total % 11
    check = (11 - remainder) % 10
    return check == digits[9]


def validate_tckn(tckn: str) -> bool:
    """TC Kimlik numarasi dogrulama (11 haneli, algoritma)."""
    tckn = re.sub(r"[^\d]", "", str(tckn))
    if len(tckn) != 11:
        return False
    if tckn[0] == "0":
        return False
    digits = [int(d) for d in tckn]
    # 10. hane kontrol
    odd_sum = sum(digits[i] for i in range(0, 9, 2))
    even_sum = sum(digits[i] for i in range(1, 8, 2))
    check10 = (odd_sum * 7 - even_sum) % 10
    if check10 != digits[9]:
        return False
    # 11. hane kontrol
    total_sum = sum(digits[:10])
    check11 = total_sum % 10
    return check11 == digits[10]


def sanitize_numeric_input(val: str) -> str:
    """Sayisal girdiyi temizle - sadece rakam, virgul, nokta, eksi birak."""
    if not val:
        return ""
    return re.sub(r"[^\d,.\-eE]", "", val)


def hash_sensitive_data(data: str) -> str:
    """Hassas veriyi hashle (loglama icin guvenli)."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


# ── Session Security ──

def generate_session_token() -> str:
    """Rastgele session token uret."""
    return hashlib.sha256(os.urandom(32)).hexdigest()


# ── CSRF Protection ──

def generate_csrf_token() -> str:
    """CSRF token uret."""
    return hashlib.sha256(os.urandom(16)).hexdigest()


def validate_csrf_token(token: str, expected: str) -> bool:
    """CSRF token dogrulama."""
    if not token or not expected:
        return False
    return hashlib.compare_digest(token, expected)
