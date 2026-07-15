import json
import os
import re
import logging

log = logging.getLogger("smmm")


def dosya_oku(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def dosya_yaz(path, data):
    import tempfile
    dir_name = os.path.dirname(path) or "."
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=dir_name, delete=False) as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp_path = tmp.name
        os.replace(tmp_path, path)
    except Exception:
        log.warning("dosya_yaz hatası: %s", path, exc_info=True)
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def parse_tutar(val):
    if not val:
        return 0.0
    try:
        s = str(val).strip()
        # OCR hata duzeltmeleri: B -> 8 (digit context), O -> 0 (digit context)
        s = re.sub(r'(\d)B', r'\g<1>8', s)
        s = re.sub(r'B(\d)', r'8\1', s)
        s = re.sub(r'(\d)O(?=\d)', r'\g<1>0', s)
        s = re.sub(r'O(?=\d)', '0', s)
        s = s.replace('I', '1').replace('l', '1')
        s = re.sub(r'[^\d,.\-]', '', s)
        if not s:
            return 0.0
        if '.' in s and ',' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            virgul_sayisi = s.count(',')
            if virgul_sayisi == 1 and re.search(r',\d{1,2}$', s):
                s = s.replace(',', '.')
            elif virgul_sayisi == 1 and re.search(r',\d{3}$', s):
                s = s.replace(',', '')
            elif virgul_sayisi >= 2:
                parcalar = s.split(',')
                if len(parcalar[-1]) == 2 and all(len(p) == 3 for p in parcalar[:-1]):
                    s = ''.join(parcalar[:-1]) + '.' + parcalar[-1]
                elif len(parcalar[-1]) == 2:
                    s = ''.join(parcalar[:-1]) + '.' + parcalar[-1]
                else:
                    s = s.replace(',', '.')
            else:
                s = s.replace(',', '.')
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def turkce_normalize(text):
    if not text:
        return text
    tr_map = {
        'İ': 'I', 'ı': 'i', 'Ş': 'S', 'ş': 's',
        'Ğ': 'G', 'ğ': 'g', 'Ü': 'U', 'ü': 'u',
        'Ö': 'O', 'ö': 'o', 'Ç': 'C', 'ç': 'c',
        'Â': 'A', 'â': 'a', 'Î': 'I', 'î': 'i',
        'Û': 'U', 'û': 'u',
    }
    for k, v in tr_map.items():
        text = text.replace(k, v)
    text = re.sub(r'[\.\,\;\:\-]{2,}', lambda m: m.group(0)[0], text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = range(len(b) + 1)
    for i, ca in enumerate(a):
        cur = [i + 1]
        for j, cb in enumerate(b):
            cur.append(min(cur[j] + 1, prev[j + 1] + 1, prev[j] + (ca != cb)))
        prev = cur
    return prev[-1]


def ocr_skorla(text):
    """OCR sonucunun kalitesini puanla. Yüksek = daha iyi."""
    if not text or len(text) < 10:
        return 0
    skor = 0
    satirlar = text.strip().split("\n")

    keywords = ["Z RAPORU", "BRUT", "BRÜT", "NET", "TOPLAM", "NAKIT", "NAKİT", "KREDI", "KREDİ", "KDV", "CIRO", "CİRO", "TUTAR", "TARIH", "TARİH", "FIS", "FİŞ"]
    keyword_hits = 0
    has_date = False
    has_tutar = False
    has_kdv = False
    decimal_count = 0
    total_lines = 0
    valid_lines = 0

    for satir in satirlar:
        ust = satir.upper()
        total_lines += 1
        harf_sayisi = len(re.findall(r'[a-zA-ZİıŞşĞğÜüÖöÇç]', ust))
        sayi_sayisi = len(re.findall(r'\d+', satir))

        for kw in keywords:
            if kw in ust:
                keyword_hits += 1
                break

        if re.search(r'\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}', satir):
            has_date = True
        if re.search(r'\d+,\d{2}', satir):
            decimal_count += 1
            has_tutar = True
        if re.search(r'KDV', ust):
            has_kdv = True
        if harf_sayisi >= 2 and sayi_sayisi > 0 and len(satir.strip()) > 4:
            valid_lines += 1

    skor += keyword_hits * 8
    if has_date:
        skor += 25
    if has_tutar:
        skor += min(decimal_count * 8, 50)
    if has_kdv:
        skor += 15

    if total_lines > 0:
        valid_ratio = valid_lines / total_lines
        if valid_ratio < 0.2:
            skor *= 0.2
        elif valid_ratio < 0.4:
            skor *= 0.5
        elif valid_ratio > 0.6:
            skor *= 1.3

    return max(0, skor)


def _tekrar_skoru(text):
    """Çok tekrar eden karakter/harf varsa (ör. noise) düşük puan ver."""
    if not text:
        return 0
    harfler = re.findall(r'[A-ZİŞĞÜÖÇ]', text.upper())
    if not harfler:
        return 0
    toplam = len(harfler)
    tekil = len(set(harfler))
    if tekil == 0:
        return 0
    return max(0, 1.0 - (tekil / max(toplam, 1)) * 5)


def _anlamsiz_kelime_orani(text):
    """Çok kısa, anlamsız kelime oranı (ör. 'a', 'b', 'E', 'K')."""
    if not text:
        return 0
    kelimeler = re.findall(r'\b\w+\b', text)
    if not kelimeler:
        return 0
    tek_harf = sum(1 for k in kelimeler if len(k) <= 2)
    return tek_harf / len(kelimeler)
