import time
import hashlib
import streamlit as st

_ocr_cache = {}
OCR_CACHE_MAX = 50
_cache_hits = 0
_cache_misses = 0


def ocr_cache_key(img_bytes):
    return hashlib.md5(img_bytes).hexdigest()


def ocr_cache_oku(key):
    return _ocr_cache.get(key)


def ocr_cache_kaydet(key, sonuc):
    global _cache_hits, _cache_misses
    if len(_ocr_cache) >= OCR_CACHE_MAX:
        eski = list(_ocr_cache.keys())[0]
        del _ocr_cache[eski]
    _ocr_cache[key] = sonuc


def ocr_cache_istatistik():
    return {
        "boyut": len(_ocr_cache),
        "limit": OCR_CACHE_MAX,
        "hits": _cache_hits,
        "misses": _cache_misses,
    }


def ocr_cache_temizle():
    global _cache_hits, _cache_misses
    _ocr_cache.clear()
    _cache_hits = 0
    _cache_misses = 0


def ocr_gorsel_isle_cached(img):
    import io as _io
    global _cache_hits, _cache_misses
    if not hasattr(st, "session_state") or "ocr_cache_stats" not in st.session_state:
        if hasattr(st, "session_state"):
            st.session_state["ocr_cache_stats"] = {"hits": 0, "misses": 0}
    buf = _io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    img_bytes = buf.getvalue()
    key = ocr_cache_key(img_bytes)
    cached = ocr_cache_oku(key)
    if cached is not None:
        _cache_hits += 1
        if hasattr(st, "session_state"):
            st.session_state["ocr_cache_stats"]["hits"] += 1
        return cached
    from ocr import ocr_gorsel_isle
    sonuc = ocr_gorsel_isle(img)
    ocr_cache_kaydet(key, sonuc)
    _cache_misses += 1
    if hasattr(st, "session_state"):
        st.session_state["ocr_cache_stats"]["misses"] += 1
    return sonuc
