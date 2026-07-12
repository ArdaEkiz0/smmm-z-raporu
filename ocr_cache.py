import time
import hashlib
import streamlit as st

_ocr_cache = {}
OCR_CACHE_MAX = 50

def ocr_cache_key(img_bytes):
    return hashlib.md5(img_bytes).hexdigest()

def ocr_cache_oku(key):
    return _ocr_cache.get(key)

def ocr_cache_kaydet(key, sonuc):
    if len(_ocr_cache) >= OCR_CACHE_MAX:
        eski = list(_ocr_cache.keys())[0]
        del _ocr_cache[eski]
    _ocr_cache[key] = sonuc

def ocr_gorsel_isle_cached(img):
    import io as _io
    buf = _io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    img_bytes = buf.getvalue()
    key = ocr_cache_key(img_bytes)
    cached = ocr_cache_oku(key)
    if cached is not None:
        return cached
    from ocr import ocr_gorsel_isle
    sonuc = ocr_gorsel_isle(img)
    ocr_cache_kaydet(key, sonuc)
    return sonuc
