import time
import hashlib
import threading

_ocr_cache = {}
OCR_CACHE_MAX = 100
_cache_hits = 0
_cache_misses = 0
_cache_lock = threading.Lock()


def ocr_cache_key(img_bytes):
    return hashlib.md5(img_bytes).hexdigest()


def ocr_cache_oku(key):
    return _ocr_cache.get(key)


def ocr_cache_kaydet(key, sonuc):
    with _cache_lock:
        if len(_ocr_cache) >= OCR_CACHE_MAX:
            # Eski %20 kayitlari temizle (LRU benzeri)
            silinecek = max(1, OCR_CACHE_MAX // 5)
            for eski in list(_ocr_cache.keys())[:silinecek]:
                del _ocr_cache[eski]
        _ocr_cache[key] = sonuc


def ocr_cache_istatistik():
    with _cache_lock:
        return {
            "boyut": len(_ocr_cache),
            "limit": OCR_CACHE_MAX,
            "hits": _cache_hits,
            "misses": _cache_misses,
        }


def ocr_cache_temizle():
    global _cache_hits, _cache_misses
    with _cache_lock:
        _ocr_cache.clear()
        _cache_hits = 0
        _cache_misses = 0


def ocr_gorsel_isle_cached(img):
    import io as _io
    global _cache_hits, _cache_misses
    buf = _io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    img_bytes = buf.getvalue()
    key = ocr_cache_key(img_bytes)
    cached = ocr_cache_oku(key)
    if cached is not None:
        with _cache_lock:
            _cache_hits += 1
        return cached
    from ocr import ocr_gorsel_isle_hibrit
    sonuc = ocr_gorsel_isle_hibrit(img)
    if isinstance(sonuc, tuple):
        sonuc = sonuc[0] if sonuc else ""
    ocr_cache_kaydet(key, sonuc or "")
    with _cache_lock:
        _cache_misses += 1
    return sonuc or ""
