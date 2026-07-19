import os
import re
import io
import logging
import numpy as np
from datetime import datetime
from PIL import Image, ImageFilter, ImageOps
from utils import log

from config import (
    DUZELTME_SOZLUK, OGRENILEN_SOZLUK, OGRENILEN_ALANLAR,
    GOT_OCR_API, BILINEN_BANKALAR, BANKA_REGEX, DATA_DIR
)
from utils import (
    dosya_oku, dosya_yaz, parse_tutar, turkce_normalize,
    levenshtein, ocr_skorla, log
)

try:
    from pyzbar.pyzbar import decode as barcode_decode
    BARCODE_MEVCUT = True
except ImportError:
    BARCODE_MEVCUT = False


def duzeltme_sozlugu():
    varsayilan = {
        "BURUT": "BRÜT", "NET": "NET", "NAK1T": "NAKIT",
        "KRED1": "KREDİ", "KRD1": "KREDİ", "KRDİ": "KREDİ",
        "KREĐI": "KREDİ", "KREĐİ": "KREDİ",
        "KAREKOD": "KAREKOD", "F1S": "FİS",
        "FPTAL": "İPTAL", "FŞ": "FİŞ", "Fİ$": "FİŞ",
        "TOPKDV": "TOPLAM KDV", "KDV MATRAH": "KDV MATRAHI",
        "MAL1YET": "MALİYET", "1ADELER": "İADELER",
        "ADELER": "İADELER", "ALACAK": "ALACAK",
        "IADELER": "İADELER", "NKT": "NAKİT",
        "YEMEKCES": "YEMEK ÇEKİ", "YEMEKCEK": "YEMEK ÇEKİ",
        "N K T": "NAKİT", "KREDKARTI": "KREDİ KARTI",
        "KRED_KART": "KREDİ KARTI",
        "KREDİ KARTI ILE": "KREDİ KARTI İLE",
        "BANKA KARTI ILE": "BANKA KARTI İLE",
        "BANKA KARŞILAMALI": "BANKA KARTI İLE",
        "BANKA KARŞILAMALI ALACAK": "BANKA KARTI İLE",
        "TOPLAM ALACAK": "TOPLAM TAHSİLAT",
        "TAHSİLAT TOPLAMI": "TOPLAM TAHSİLAT",
        "KUM TOPLAM": "KÜM TOPLAM",
        "KUMULATIF TOPLAM": "KÜMÜLATİF TOPLAM",
        "EKRAN ORTU": "EKRAN ÜSTÜ",
        "EKORAN ÜSTÜ": "EKRAN ÜSTÜ",
        "EKRAN ORTUS": "EKRAN ÜSTÜ",
        "BILGI FIRMA": "BİLGİ FİRMA",
        "ALICI FIRMA": "ALICI FİRMA",
        "FIRMA ADI": "FİRMA ADI",
        "Tarih": "Tarih", "TARIH": "TARİH",
        "TARIHI": "TARİHİ", "TARİHİ": "TARİHİ",
        "SAAT": "SAAT", "BELGE NO": "BELGE NO",
    }
    dosya = dosya_oku(DUZELTME_SOZLUK, {})
    varsayilan.update(dosya)
    return varsayilan


def ogrenilen_sozluk():
    return dosya_oku(OGRENILEN_SOZLUK, {})


def duzeltme_ogren(yanlis, dogru):
    sozluk = ogrenilen_sozluk()
    sozluk[yanlis.strip().upper()] = dogru.strip()
    dosya_yaz(OGRENILEN_SOZLUK, sozluk)


def ogrenci_alan_bul(ham_text, alan_adi, dogru_deger):
    if not ham_text or not dogru_deger:
        return None
    satirlar = ham_text.split("\n")
    for satir in satirlar:
        satir = satir.strip()
        if not satir:
            continue
        l = levenshtein(satir.upper(), dogru_deger.upper())
        if l <= 3:
            return satir
    for satir in satirlar:
        satir = satir.strip()
        if not satir:
            continue
        l = levenshtein(satir.upper()[:len(dogru_deger)], dogru_deger.upper())
        if l <= 2:
            return satir
    return None


def ogrenilen_alanlar():
    return dosya_oku(OGRENILEN_ALANLAR, {})


def ogr_alan_kaydet(alan_adi, deger):
    alanlar = ogrenilen_alanlar()
    deger = deger.strip()
    if not deger:
        return
    if alan_adi not in alanlar:
        alanlar[alan_adi] = deger
    else:
        eski = alanlar[alan_adi]
        if eski != deger:
            alanlar[alan_adi] = deger
    dosya_yaz(OGRENILEN_ALANLAR, alanlar)


def _alan_copuk_mu(deger):
    if not deger or len(deger) < 2:
        return True
    if len(deger) > 50:
        return True
    ok_karakter = sum(1 for c in deger if c.isalnum() or c in " .-/")
    if ok_karakter / max(len(deger), 1) < 0.5:
        return True
    return False


def ogr_alanlari_uygula(parsed):
    alanlar = ogrenilen_alanlar()
    for alan, deger in alanlar.items():
        if alan in parsed:
            mevcut = parsed[alan]
            if not mevcut or _alan_copuk_mu(str(mevcut)):
                parsed[alan] = deger


def duzeltme_uygula(text):
    sozluk = duzeltme_sozlugu()
    ogr = ogrenilen_sozluk()
    hepsi = {**sozluk, **ogr}
    sorted_keys = sorted(hepsi.keys(), key=len, reverse=True)
    for yanlis in sorted_keys:
        dogru = hepsi[yanlis]
        if not yanlis or not dogru:
            continue
        text = re.sub(r'(?<!\w)' + re.escape(yanlis) + r'(?!\w)', dogru, text, flags=re.IGNORECASE)

    turkce_patterns = [
        (r'\bKREĐ[İI]\b', 'KREDİ'),
        (r'\bKR[İI]D[İI]\b', 'KREDİ'),
        (r'\bKRE[DĐ][İI]\b', 'KREDİ'),
        (r'\bNAK[İI]T\b', 'NAKİT'),
        (r'\bT[İI]AR[İI]H[İI]?\b', 'TARİHİ'),
        (r'\b[ĞG][ÜU]N[ÜU]M[ÜU]Z\b', 'GÜNÜMÜZ'),
        (r'\bD[ÖO]K[ÜU]M[ÜU]N\b', 'DÖKÜMÜN'),
        (r'\b[ÜU]R[ÜU]N\b', 'ÜRÜN'),
        (r'\b[İI1]ADE[Ll][Ee][Rr]\b', 'İADELER'),
        (r'\b[İI1]A[DĐ]E[LŁ]?[İI]?\b', 'İADE'),
        (r'\bF[İI][ŞS]\b', 'FİŞ'),
        (r'\bF[İI]Ş[İI]?\b', 'FİŞ'),
        (r'\b[ĞG][ÜU]MR[ÜU]K\b', 'GÜMRÜK'),
        (r'\b[ÇC][ÖO]K\b', 'ÇOK'),
        (r'\b[B8][R8][ÜU][T7]\b', 'BRÜT'),
        (r'\bTOPKDV\b', 'TOPLAM KDV'),
        (r'\bKUM[\s-]?TOP\b', 'KÜM TOPLAM'),
        (r'\bKUMULAT[İI]F\b', 'KÜMÜLATİF'),
        (r'\bEKRAN[\s-]?[O0Q]R[T7][ÜU]\b', 'EKRAN ÜSTÜ'),
        (r'\bMA[LŁ]?[İI]YE[T7]\b', 'MALİYET'),
        (r'\b[VV][ÖO]R[ÇC][İI]\b', 'VORÇİ'),
        (r'\b[ÖO]DE[MV][E3]\b', 'ÖDEME'),
        (r'\b[Aa]L[İI][ÇC][İI]\b', 'ALICI'),
        (r'\bSA[T7][Iİ][ÇC][Iİ]\b', 'SATIÇI'),
        (r'TOPLAM\s+[S5](?=\d)', 'TOPLAM %'),
        (r'KDV\s+[S5](?=\d)', 'KDV %'),
        (r'\bMktr\b', '%'),
        (r'\b[45][LŁ][45][CÇ][4A][K]\b', 'ALACAK'),
        (r'\b[6G][4A][R8][4A][N][T7][İI]\b', 'GARANTİ'),
        (r'\b[5S][4A][T7][İI][ŞS]\b', 'SATIŞ'),
        (r'\bTAH[5S][1İI][LŁ][4A][T7]\b', 'TAHSİLAT'),
        (r'\bKRED[İI][K][4A][R8][T7][İI]\b', 'KREDİ KARTI'),
        (r'\bNAK[İI][T7][O0]D[E3][M][E3]\b', 'NAKİT ÖDEME'),
        (r'\b[MN][ÜU][ŞS][T7][E3][R8][İI1]\b', 'MÜŞTERİ'),
        (r'\b[İI1][ŞS][LŁ][E3][M]\b', 'İŞLEM'),
        (r'\b[İI1][ŞS][Y][E3][R8][İI1]\b', 'İŞYERİ'),
        (r'\bD[İI1][ĞG][E3][R8]\b', 'DİĞER'),
        (r'\bB[İI1][M]\b', 'BİM'),
        (r'\b[ŞS][O0][K]\b', 'ŞOK'),
        (r'\bF[İI1][R8][M][4A]\b', 'FİRMA'),
        (r'\bBEL[G6][E3]\s*NO\b', 'BELGE NO'),
        (r'\b[T7][O0][P][LŁ][4A][M]\b', 'TOPLAM'),
        (r'\b[O0][R8][T7][4A][K]\s*[LŁ][I1][ĞG][İI1]\b', 'ORTAKLIK'),
    ]
    for pat, repl in turkce_patterns:
        text = re.sub(pat, repl, text)

    text = text.replace("BURUT", "BRÜT")
    text = text.replace("BRUТ", "BRÜT")
    text = text.replace("BRUT", "BRÜT")
    return text


def _deskew(img):
    """Yamuk görüntüyü düzeltir (OpenCV minAreaRect ile)."""
    try:
        import cv2
        import numpy as np
        arr = np.array(img)
        if arr.ndim == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        inv = cv2.bitwise_not(arr)
        thresh = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 100:
            return img
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.5 or abs(angle) > 15:
            return img
        h, w = arr.shape
        center = (w // 2, h // 2)
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(arr, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return Image.fromarray(rotated)
    except Exception:
        return img


def _clahe(img):
    """CLAHE ile lokal kontrast artırma (düşük ışık için)."""
    try:
        import cv2
        import numpy as np
        arr = np.array(img)
        if arr.ndim == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(arr)
        return Image.fromarray(enhanced)
    except Exception:
        return img


def _bilateral_denoise(img):
    """Kenar koruyucu gürültü azaltma."""
    try:
        import cv2
        import numpy as np
        arr = np.array(img)
        if arr.ndim == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        denoised = cv2.bilateralFilter(arr, 5, 50, 50)
        return Image.fromarray(denoised)
    except Exception:
        return img


def _remove_border(img):
    """Fiş kenarlarındaki siyah çerçeveyi kırpar."""
    try:
        import cv2
        import numpy as np
        arr = np.array(img)
        if arr.ndim == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        if w < arr.shape[1] * 0.5 or h < arr.shape[0] * 0.5:
            return img
        margin = 5
        x = max(0, x + margin)
        y = max(0, y + margin)
        w = min(arr.shape[1] - x, w - 2 * margin)
        h = min(arr.shape[0] - y, h - 2 * margin)
        cropped = arr[y:y + h, x:x + w]
        return Image.fromarray(cropped)
    except Exception:
        return img


def gorsel_hazirla(img, mode="default", min_w=None):
    """Gelişmiş görüntü ön işleme.

    Modlar:
      - default: orijinal pipeline (CLAHE + deskew + upscale + denoise + sharpen)
      - sayisal: sayı alanları için (yüksek kontrast, agresif threshold)
      - kalin: kalın/büyük fontlar (CLAHE + upscale)
    """
    if img.mode != 'L':
        img = img.convert('L')

    w, h = img.size

    if min_w is None:
        min_w = 1200 if mode != "sayisal" else 1500

    if mode == "sayisal":
        img = _bilateral_denoise(img)
        img = _clahe(img)
        if w < 1500 or h < 800:
            faktor = max(min_w / max(w, 1), 2.5)
            w2, h2 = int(w * faktor), int(h * faktor)
            img = img.resize((w2, h2), Image.LANCZOS)
        img = img.filter(ImageFilter.MedianFilter(3))
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=3))
        return img

    if mode == "kalin":
        if w < min_w or h < 600:
            faktor = max(min_w / max(w, 1), 2.0)
            w2, h2 = int(w * faktor), int(h * faktor)
            img = img.resize((w2, h2), Image.LANCZOS)
        img = _clahe(img)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=3))
        return img

    img = _deskew(img)
    img = _remove_border(img)
    img = _bilateral_denoise(img)
    img = _clahe(img)

    w, h = img.size
    if w < min_w or h < 600:
        faktor = max(min_w / max(w, 1), 2.0)
        w2, h2 = int(w * faktor), int(h * faktor)
        img = img.resize((w2, h2), Image.LANCZOS)

    img = img.filter(ImageFilter.MedianFilter(3))
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    return img


def ocr_guvenli(img, psm=6, config_extra=""):
    import pytesseract
    custom = f"--oem 1 --psm {psm} -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzİıŞşĞğÜüÖöÇç%.,:;/-₺TL " + config_extra
    try:
        data = pytesseract.image_to_data(img, lang="tur", config=custom, output_type=pytesseract.Output.DICT)
        metin = ""
        for i, word in enumerate(data["text"]):
            conf = int(data["conf"][i])
            if conf >= 20 and word.strip():
                metin += word + " "
            elif conf >= 0 and word.strip():
                metin += word + " "
            else:
                metin += "\n" if data["text"][i] == "" else ""
        return metin.strip()
    except Exception:
        log.warning("OCR güvenli metin çıkarma başarısız", exc_info=True)
        return ""


_otsu_engine = None

def load_ocr():
    global _otsu_engine
    import pytesseract
    import shutil as _shutil
    tesseract_yolu = _shutil.which("tesseract")
    if tesseract_yolu:
        pytesseract.pytesseract.tesseract_cmd = tesseract_yolu
    else:
        tesseract_yollari = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
        ]
        for yl in tesseract_yollari:
            if os.path.exists(yl):
                pytesseract.pytesseract.tesseract_cmd = yl
                break
    try:
        pytesseract.get_tesseract_version()
        _otsu_engine = pytesseract
        return _otsu_engine
    except Exception:
        log.warning("Tesseract OCR motoru bulunamadı", exc_info=True)
        return None


def got_ocr_api(url):
    if not url:
        return ""
    try:
        import requests
        resp = requests.post(f"{url.rstrip('/')}/ocr", json={"image": ""}, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("text", "")
    except Exception:
        log.warning("GOT OCR API çağrısı başarısız", exc_info=True)
    return ""


def got_ocr_api_saglik(url):
    if not url:
        return False
    try:
        import requests
        resp = requests.get(f"{url.rstrip('/')}/health", timeout=10)
        return resp.status_code == 200
    except Exception:
        log.warning("GOT OCR sağlık kontrolü başarısız", exc_info=True)
        return False


def _otsu_threshold(img):
    import numpy as np
    arr = np.array(img)
    if arr.ndim == 3:
        import cv2
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    total = arr.size
    hist = np.bincount(arr.ravel(), minlength=256)
    sum_all = np.dot(np.arange(256), hist)
    sum_b = 0
    w_b = 0
    w_f = 0
    max_var = 0
    best_t = 0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > max_var:
            max_var = var
            best_t = t
    return best_t


def _ocr_hazirla_otsu(img, offset=0):
    import cv2
    import numpy as np
    img_cv = np.array(img.convert("L"))
    t = _otsu_threshold(img)
    t = max(0, min(255, t + offset))
    _, thresh = cv2.threshold(img_cv, t, 255, cv2.THRESH_BINARY)
    return Image.fromarray(thresh)


def ocr_image(img):
    """Ana OCR pipeline - once hizli denemeler, sonra kapsamli."""
    candidates = []
    try_hazir = img.copy()

    modes = [
        ("default", [0, -5, 5]),
        ("kalin", [0]),
    ]

    for mode_name, offsets in modes:
        hazir = gorsel_hazirla(img, mode=mode_name, min_w=1200)
        for offset in offsets:
            otsu = _ocr_hazirla_otsu(hazir, offset)
            for psm in [6, 4]:
                text = ocr_guvenli(otsu, psm=psm)
                if text:
                    text = ocr_duzelt(text)
                    score = ocr_skorla(text)
                    candidates.append((score, psm, mode_name, len(text), text))
                    if score >= 200:
                        return text

    if not candidates or (candidates and candidates[0][0] < 100):
        for mode_name, offsets in [("default", [-10, 10]), ("sayisal", [0])]:
            hazir = gorsel_hazirla(img, mode=mode_name, min_w=1200)
            for offset in offsets:
                otsu = _ocr_hazirla_otsu(hazir, offset)
                for psm in [6, 4, 3]:
                    text = ocr_guvenli(otsu, psm=psm)
                    if text:
                        text = ocr_duzelt(text)
                        score = ocr_skorla(text)
                        candidates.append((score, psm, mode_name, len(text), text))
                        if score >= 200:
                            return text

    if candidates:
        candidates.sort(key=lambda x: (-x[0], -x[3]))
        best_score, _, _, _, best_text = candidates[0]
    else:
        best_text, best_score = "", -1

    if best_text:
        dup_control = True
        while dup_control:
            dup_control = False
            lines = best_text.split("\n")
            for i in range(1, len(lines)):
                if lines[i].strip() == lines[i - 1].strip() and len(lines[i].strip()) > 5:
                    lines.pop(i)
                    dup_control = True
                    break
            best_text = "\n".join(lines)

    if best_score < 50:
        for rot in [90, 270]:
            rotated = gorsel_hazirla(img.rotate(rot, expand=True), mode="default")
            for offset in [0]:
                otsu = _ocr_hazirla_otsu(rotated, offset)
                for psm in [6]:
                    text = ocr_guvenli(otsu, psm=psm)
                    if text:
                        text = ocr_duzelt(text)
                        score = ocr_skorla(text)
                        if score > best_score:
                            best_score = score
                            best_text = text

    return best_text


def ocr_gorsel_isle(img):
    return ocr_image(img)


# EasyOCR lazy loader - ilk kullanimda yuklenir.
# Streamlit uzerinde calistiginda @st.cache_resource ile paylasilir;
# yoksa process-local global kullanilir.
_easyocr_reader = None
_easyocr_available = None


def _get_easyocr():
    """EasyOCR reader'i lazy-load et, hata olursa None don."""
    try:
        import streamlit as st
    except ImportError:
        st = None

    # Streamlit icinde calisiyorsa cache_resource kullan (cross-session paylasim)
    if st is not None:
        @st.cache_resource(show_spinner=False)
        def _streamlit_easyocr():
            try:
                import easyocr
                return easyocr.Reader(['tr', 'en'], gpu=False, verbose=False)
            except Exception as e:
                log.warning(f"EasyOCR yuklenemedi: {e}")
                return None
        return _streamlit_easyocr()

    # Streamlit yoksa (CLI/test) process-local global kullan
    global _easyocr_reader, _easyocr_available
    if _easyocr_available is False:
        return None
    if _easyocr_reader is not None:
        return _easyocr_reader
    try:
        import easyocr
        _easyocr_reader = easyocr.Reader(['tr', 'en'], gpu=False, verbose=False)
        _easyocr_available = True
        return _easyocr_reader
    except Exception as e:
        log.warning(f"EasyOCR yuklenemedi: {e}")
        _easyocr_available = False
        return None


def easyocr_gorsel_isle(img):
    """EasyOCR ile gorsel oku, sonucu text olarak don."""
    reader = _get_easyocr()
    if reader is None:
        return ""
    try:
        img_array = np.array(img)
        results = reader.readtext(img_array, detail=0, paragraph=False)
        return "\n".join(results)
    except Exception as e:
        log.warning(f"EasyOCR okuma hatasi: {e}")
        return ""


def ocr_capraz_dogrula(tess_text, easy_text, tess_parsed, easy_parsed):
    """Tesseract ve EasyOCR ciktilarini karsilastir, guven puani guncelle.
    
    Her iki motor ayni degeri bulduysa yuksek guven.
    Farkli deger bulduysa dusuk guven, ogrenme sistemine bildir.
    """
    from ogrenme_cekirdigi import duzeltme_kaydet
    karsilastir = [
        ("brut", "brut"),
        ("net_toplam", "net_toplam"),
        ("nakit", "nakit"),
        ("kredi_karti", "kredi_karti"),
        ("iadeler", "iadeler"),
    ]
    for alan, _ in karsilastir:
        tv = tess_parsed.get(alan, 0) or 0
        ev = easy_parsed.get(alan, 0) or 0
        if tv > 0 and ev > 0 and abs(tv - ev) < 0.01:
            continue
        if tv > 0 and ev > 0 and abs(tv - ev) > 100:
            diff_note = f"{alan}: Tesseract={tv}, Easy={ev}"
            log.info(f"OCR capraz fark: {diff_note}")
            if tess_parsed.get("_kaynak") != "easyocr" and "tess" not in tess_parsed:
                duzeltme_kaydet(str(tv), str(ev), alan_adi=alan, kaynak="otomatik")


def ocr_gorsel_isle_hibrit(img):
    """Tesseract + EasyOCR hibrit: Tess yeterliyse EasyOCR'a gerek yok."""
    tess_text = ocr_image(img)
    tess_score = ocr_skorla(tess_text)
    tess_parsed = parse_z_raporu(tess_text)
    tess_kk = tess_parsed.get("kredi_karti", 0)
    tess_brut = tess_parsed.get("brut", 0)

    HIGH_CONF = 150
    if tess_score >= HIGH_CONF:
        if tess_kk > 0 or tess_brut <= 0:
            return tess_text

    easy_text = easyocr_gorsel_isle(img)
    if not easy_text:
        return tess_text
    easy_score = ocr_skorla(easy_text)
    easy_parsed = parse_z_raporu(easy_text)

    try:
        ocr_capraz_dogrula(tess_text, easy_text, tess_parsed, easy_parsed)
    except Exception:
        pass

    easy_kk = easy_parsed.get("kredi_karti", 0)
    if tess_kk == 0 and easy_kk > 0:
        return easy_text
    if easy_score > tess_score + 20:
        return easy_text
    if tess_kk > 0:
        return tess_text
    return tess_text


# Initialize OCR engine on module load
ocr_engine = load_ocr()


def ocr_oku_ve_duzelt(img, dogrulama_yap: bool = True,
                       mukellef_listesi: list = None,
                       urun_kodlari: list = None) -> dict:
    """OCR + otomatik duzeltme + dogrulama pipeline'i.

    Returns:
        {
            "ham_text": "...",
            "duzeltilmis_text": "...",
            "parsed": {...},
            "otomatik_duzeltmeler": [...],
            "alan_duzeltmeleri": [...],
            "dogrulama": {...}  # ocr_dogrulama ciktisi (varsa)
            "skor": N,
        }
    """
    from ogrenme_cekirdigi import auto_duzeltme_uygula, alan_duzeltme_uygula
    from ocr_dogrulama import ocr_sonuc_dogrula

    # 1. OCR
    ham_text = ocr_gorsel_isle_hibrit(img)
    skor = ocr_skorla(ham_text)

    # 2. Otomatik duzeltme (ogrenilmis sozluk)
    duzeltilmis_text, otomatik_duzeltmeler = auto_duzeltme_uygula(ham_text)

    # 3. Parse
    parsed = parse_z_raporu(duzeltilmis_text)
    parsed["ham_text"] = ham_text

    # 4. Alan bazli duzeltme
    parsed, alan_duzeltmeleri = alan_duzeltme_uygula(parsed)

    # 5. Dogrulama
    dogrulama = None
    if dogrulama_yap:
        dogrulama = ocr_sonuc_dogrula(
            parsed, ham_text=ham_text,
            mukellef_listesi=mukellef_listesi,
            urun_kodlari=urun_kodlari,
        )

    # 6. Ogrenme: duzeltilen metindeki degisiklikleri ogren
    if otomatik_duzeltmeler:
        for d in otomatik_duzeltmeler:
            if d.get("uygulandi"):
                from ogrenme_cekirdigi import duzeltme_kaydet
                duzeltme_kaydet(
                    d["yanlis"], d["dogru"],
                    alan_adi="", kaynak="otomatik"
                )

    return {
        "ham_text": ham_text,
        "duzeltilmis_text": duzeltilmis_text,
        "parsed": parsed,
        "otomatik_duzeltmeler": otomatik_duzeltmeler,
        "alan_duzeltmeleri": alan_duzeltmeleri,
        "dogrulama": dogrulama,
        "skor": skor,
    }


def banka_bul(text):
    if not text:
        return None
    for banka in BILINEN_BANKALAR:
        if banka.lower() in text.lower():
            return banka
    for pat, adi in BANKA_REGEX:
        if re.search(pat, text, re.IGNORECASE):
            return adi
    if "MULTINET" in text.upper() or "multinet" in text.lower():
        return "Multinet"
    if "SODEXO" in text.upper():
        return "Sodexo"
    if "SETCARD" in text.upper() or "SET CARD" in text.upper():
        return "Setcard"
    if "TICKET" in text.upper() and "RESTAURANT" in text.upper():
        return "Ticket Restaurant"
    if re.search(r'T[ÜU]RK[İI]YE\s*[İI][ŞS]\s*BANKAS[İI]', text, re.IGNORECASE):
        return "İş Bankası"
    return None


def barkod_oku(img):
    if not BARCODE_MEVCUT:
        return []
    sonuc = []
    try:
        decoded = barcode_decode(img)
        for d in decoded:
            sonuc.append({"type": d.type, "data": d.data.decode("utf-8", errors="replace")})
    except Exception:
        log.warning("Barkod çözümleme başarısız", exc_info=True)
    return sonuc


def salon_bul(text):
    if not text:
        return ""
    satirlar = [s.strip() for s in text.strip().split("\n") if s.strip()]
    for satir in satirlar:
        s = satir.strip()
        if re.search(r'(?:BILGI|ALICI|FIRMA|UNVAN)[:\-]?\s*(.+)', s, re.IGNORECASE):
            eslesme = re.search(r'(?:BILGI|ALICI|FIRMA|UNVAN)[:\-]?\s*(.+)', s, re.IGNORECASE)
            if eslesme:
                ad = eslesme.group(1).strip()
                ad = re.sub(r'\s+', ' ', ad)
                if len(ad) > 3 and not ad.isdigit():
                    return ad

    skip_patterns = [
        r'(?:TAR[İI]H|SAAT|F[İI]Ş|Z\s*NO|Z\s*RAPORU|EK[ÜU]\s*NO|BELGE|VKN|TC|TEL|FAX|VERG[İI]|DA[İI]RE|MAHALLE|SOKAK|CADDE|APT|NO[:/])',
        r'^\d+[\.,]?\d*\s*$',
        r'^\d{2}[./]\d{2}[./]\d{2,4}',
        r'^\d{1,2}:\d{2}',
        r'^\d+\s*\*',
        r'(?:TEŞEKK[ÜU]R|HAYIRLI|İY[İI] G[ÜU]NLER|HOŞGELD[İI]N[İI]Z)',
        r'(?:B[İI]LG[İI]|M[İI]Z[İI]|G[ÖO]REVL[İI]|ADRES|VKN|TCKN|T\.C\.|ŞUBE|MAĞAZA)',
        r'(?:MLZ|ALIM|SATIM|TOPTAN|PERAKENDE|T[İI]C)',
        r'(?:FATURA|TAHS[İI]LAT|ÖDEME|F[İI]ŞNO|SAYACI|SAYAC)',
        r'^\d{1,2}[\.\s]*[A-Z]{3,}',
        r'(?:MH\.|SK\.|CD\.|CAD\.|SOK\.|MAH\.)',
        r'^\d{2,}',
        r'(?:K[İI]RAZ|[İI]ZM[İI]R|[İI]STANBUL|ANKARA)',
        r'(?:RAPOR|G[ÜU]N|G[ÜU]NL[ÜU]K|Z\s*G[ÜU]N|F[İI]Ş|TOPLAM|NAK[İI]T|KART|TUTAR|SAYI)',
        r'(?:VD|TC|VKN)',
        r'(?:PINAR|CADDE|SOKAK|MEZBAH|ÇAY|KAHVE|TOST|MESRUBAT|T\.GIDA|T\.EKMEK|SIGARA|YA[PĞ]|MEYVE|SEBZE|MEYVE&SEBZE|SEBZESMEYVE)',
        r'.*[^\x20-\x7E\xc0-\xff].*',  # Garbled chars (binary noise)
    ]

    firma_adaylari = []
    for satir in satirlar[:8]:
        s = satir.strip()
        if len(s) < 4 or len(s) > 60:
            continue
        if any(re.search(p, s, re.IGNORECASE) for p in skip_patterns):
            continue
        harf_sayisi = len(re.findall(r'[a-zA-ZİıŞşĞğÜüÖöÇç]', s))
        if harf_sayisi < 4:
            continue
        # Skip if has too many garbled chars
        garbled_sayisi = len(re.findall(r'[^\x20-\x7E\xc0-\xff]', s))
        if garbled_sayisi > 2:
            continue
        if s.isupper() or s.istitle():
            firma_adaylari.append(s)
        elif len(s.split()) <= 4 and harf_sayisi >= 5:
            firma_adaylari.append(s)

    if firma_adaylari:
        oncelik = []
        for aday in firma_adaylari:
            kelimeler = aday.split()
            puan = len(aday) + len(kelimeler) * 5
            if any(k in ['MARKET', 'MAĞAZA', 'MAGAZA', 'BAKKAL', 'MARKETI'] for k in kelimeler):
                puan += 100
            if any(k in ['LTD', 'ŞTİ', 'A.Ş.', 'AS'] for k in kelimeler):
                puan -= 50
            if any(c in aday for c in [':', '/']):
                puan -= 30
            # Bonus for having only letters and spaces
            if re.match(r'^[A-ZÇĞIİÖŞÜa-zçğıöşü\s]+$', aday):
                puan += 30
            oncelik.append((puan, aday))

        en_iyi = max(oncelik)[1]
        return en_iyi

    return ""


def salon_bul_fallback(text, mukellef_listesi):
    if not text or not mukellef_listesi:
        return ""
    t_duz = turkce_normalize(text.upper())
    for m in mukellef_listesi:
        ad = turkce_normalize(m.get("adi", "").upper())
        if ad and ad in t_duz:
            return m["adi"]
        ka = turkce_normalize(m.get("kisa_adi", "").upper())
        if ka and ka in t_duz:
            return m["adi"]
    return ""


def ocr_duzelt(text):
    if not text:
        return text
    text = duzeltme_uygula(text)
    text = re.sub(r'[B8]\s*R\s*[UÜ]\s*T', 'BRÜT', text, flags=re.IGNORECASE)
    text = re.sub(r'(?<!\w)BURUT(?!\w)', 'BRÜT', text)
    text = re.sub(r'TOPLAM\s+KDV', 'TOPLAM KDV', text, flags=re.IGNORECASE)
    text = re.sub(r'NET\s+TUTAR', 'NET TUTAR', text, flags=re.IGNORECASE)
    text = re.sub(r'Net\s+Tutar', 'Net Tutar', text)
    text = re.sub(r'KRED[İI]\s*KART[İIı]\s*[İIı]*LE', 'KREDİ KARTI İLE', text, flags=re.IGNORECASE)
    text = re.sub(r'BANKA\s*KART[İIı]\s*[İIı]*LE', 'BANKA KARTI İLE', text, flags=re.IGNORECASE)
    text = re.sub(r'BANKA\s*KARŞILAMALI', 'BANKA KARTI İLE', text, flags=re.IGNORECASE)
    # OCR bozuk okumalarini duzelt
    text = re.sub(r'\bBALTVER\b', 'MALİ VERİ', text)
    text = re.sub(r'\bBALT\s*V[İI]R[İI]\b', 'MALİ VERİ', text)
    text = re.sub(r'\bTOPLAN\b', 'TOPLAM', text)
    text = re.sub(r'\bTOPLAN\s*TUTAR\b', 'TOPLAM TUTAR', text)
    text = re.sub(r'\bNaktu?\s*B[İI]T[İI]?[İI]L[İI]\b', 'NAKİT BEDELİ', text)
    text = re.sub(r'\bNAKIT\s*B[İI]TL[İI]\b', 'NAKİT BEDELİ', text)
    text = re.sub(r'\bTEEKKK?R[FE]?D[FE]?R[Z]\b', 'TEŞEKKÜR EDERİZ', text)
    text = re.sub(r'\bT[FE]Ş[FE]KK[ÜU]R\s*[FE]D[FE]R[İI]Z\b', 'TEŞEKKÜR EDERİZ', text)
    text = re.sub(r'\bT[E3][ŞS][E3]KK[UÜ][R]\s*[E3]D[E3][R][İI1][Z]\b', 'TEŞEKKÜR EDERİZ', text)
    # TL varyasyonlari (TI, T1, Tl -> TL)
    text = re.sub(r'(?<=\d)\s*[T][I1l](?=\s)', ' TL', text)
    text = re.sub(r'(?<=\d)\s*[T][I1l]\b', ' TL', text)
    text = re.sub(r'\bT[I1l](?=\s*\d)', 'TL', text)
    # Karisik kart isimleri
    text = re.sub(r'K[.]?\s*[K][Aa][Rr][Tt][I1ı]?\s*[İIı]?[lL]?[eE]?', 'K.KARTİ', text)
    text = re.sub(r'\bKART[İI]\s*[İI][L][E]\b', 'KARTI İLE', text)
    text = re.sub(r'\bNAK[İI][T7]\s*[İI][L][E]\b', 'NAKİT İLE', text)
    # sayi karisikliklari
    text = re.sub(r'(\d)[O0Ö]', r'\g<1>0', text)
    text = re.sub(r'[O0Ö]([.,]\d)', r'0\g<1>', text)
    text = re.sub(r'\b[S5](?=[.,]\d)', '5', text)
    text = re.sub(r'(?<=\d)[S5]\b', '5', text)
    text = re.sub(r'\b[B8](?=[.,]\d)', '8', text)
    text = re.sub(r'(?<=\d)[B8]\b', '8', text)
    return text


def parse_z_raporu(text):
    sonuc = {
        "tarih": "", "z_no": "", "belge_no": "", "firma_adi": "",
        "banka_adi": "", "brut": 0.0, "net_toplam": 0.0,
        "nakit": 0.0, "kredi_karti": 0.0, "yemek_ceki": 0.0,
        "iadeler": 0.0, "toplam_tahsilat": 0.0,
        "urunler": [], "kdv_kalemleri": [], "ham_text": text,
    }
    if not text:
        return sonuc

    t_duz = turkce_normalize(text)
    t_duz = ocr_duzelt(t_duz)

    # Tarih
    tarih_pat = [
        (r'TAR[İI]H[İI1]?[:\-]?\s*([0-9Il]{1,2})[\s./\-]+([0-9IlOo]{1,2})[\s./\-]+([0-9BOIlOoQD]{2,4})', True),
        (r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})\s*(?:TAR[İI]H|SAAT)', True),
        (r'TAR[\.\s]*[:\-]?\s*(\d{1,2})[\s./\-]+(\d{1,2})[\s./\-]+(\d{2,4})', True),
        (r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})', True),
        (r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{2})(?!\d)', True),
        (r'([0-9Il]{1,2})[\./]([0-9IlOo]{1,2})[\./]([0-9BOIlOoQD]{4})', True),
        (r'[\w\s]{0,5}(\d{1,2})[./](\d{1,2})[./](\d{4})', True),
        (r'\b(\d{1,2})[./](\d{4})\b', False),
    ]
    ilk_satirlar = "\n".join(t_duz.split("\n")[:15])
    arama_alani = ilk_satirlar if ilk_satirlar.strip() else t_duz
    for pat, has_day in tarih_pat:
        m = re.search(pat, arama_alani)
        if not m:
            m = re.search(pat, t_duz)
        if m:
            try:
                if has_day:
                    gun_str, ay_str, yil_str = m.group(1), m.group(2), m.group(3)
                else:
                    ay_str, yil_str = m.group(1), m.group(2)
                    gun_str = "01"
                gun_str = re.sub(r'[Il]', '1', gun_str)
                gun_str = re.sub(r'[Oo]', '0', gun_str)
                ay_str = re.sub(r'[Oo]', '0', ay_str)
                ay_str = re.sub(r'[Il]', '1', ay_str)
                yil_str = yil_str.replace('I', '1').replace('l', '1').replace('O', '0').replace('o', '0').replace('B', '6').replace('Q', '0').replace('D', '0')
                gun = int(gun_str)
                ay = int(ay_str)
                yil = int(yil_str)
                if yil < 100:
                    yil = 2000 + yil if yil < 50 else 1900 + yil
                if yil < 1900 or yil > 2100:
                    if 100 < yil < 1000:
                        continue
                if gun < 1 or gun > 31 or ay < 1 or ay > 12:
                    continue
                dt = datetime(yil, ay, gun)
                sonuc["tarih"] = dt.strftime("%d.%m.%Y")
                break
            except (ValueError, IndexError):
                continue

    # Z No
    z_pat = [
        r'Z\s*NO[:\-]?\s*(\d{1,4}(?:[./]\d{1,4})?)',
        r'Z\s*RAPORU[:\-]?\s*NO[:\-]?\s*(\d{1,4}(?:[./]\d{1,4})?)',
        r'[Zz]\s*[Nn][Oo][:\-]?\s*(\d{1,4}(?:[./]\d{1,4})?)',
        r'Z\.?\s*SAYA[CÇ][:\-]?\s*(\d{1,4}(?:[./]\d{1,4})?)',
        r'Z\.?\s*SAYA[CÇ]\s+(\d{1,4}(?:[./]\d{1,4})?)',
        r'Z\s*SAYAC[^\d]*(\d{1,4}(?:[./]\d{1,4})?)',
    ]
    for pat in z_pat:
        m = re.search(pat, t_duz, re.IGNORECASE)
        if m:
            sonuc["z_no"] = m.group(1).strip()
            break

    # Belge No
    belge_pat = [
        r'(?:F[İIŞ]S?|FIS|BELGE)\s*NO[:\-]?\s*(\d+)',
        r'(?:F[İIŞ]S?|FIS|BELGE)\s*[Nn][Oo][:\-]?\s*(\d+)',
        r'(?:F[İIŞ]S?|FIS)\s*[:\-]\s*[Nn]o[:\-]?\s*(\d+)',
        r'(?:F[İIŞ]S?|FIS)\s+(?=[Nn][Oo])(\d{2,6})',
        r'F[İIŞ]S?[\.\s]+[Nn][Oo][:\-]?\s*(\d{2,6})',
        r'F\s+No[:\-]?\s*(\d+)',
    ]
    for pat in belge_pat:
        m = re.search(pat, t_duz, re.IGNORECASE)
        if m:
            start_pos = m.start()
            oncesi = t_duz[max(0, start_pos-15):start_pos].upper()
            if any(x in oncesi for x in ['TERMINAL', 'ISYERI', 'İŞYERİ', 'IŞYERI']):
                continue
            sonuc["belge_no"] = m.group(1).strip()
            break
    if not sonuc["belge_no"]:
        fis_no_match = re.search(r'(?:^|\s)(?:F[İIŞ]?S?[\.\s]*[Nn][Oo]|F[\.\s]+[Nn]o|Fiş[\.\s]*[Nn]o)[:\s]*(\d{2,6})', t_duz, re.IGNORECASE | re.MULTILINE)
        if fis_no_match:
            start_pos = fis_no_match.start()
            oncesi = t_duz[max(0, start_pos-15):start_pos].upper()
            if not any(x in oncesi for x in ['TERMINAL', 'ISYERI', 'İŞYERİ', 'IŞYERI']):
                sonuc["belge_no"] = fis_no_match.group(1).strip()
    if not sonuc["belge_no"]:
        ilk_3_satir = "\n".join(t_duz.split("\n")[:3])
        fis_ilk_match = re.search(r'F[İIŞ]?S?\s*[Nn][Oo][:\-]?\s*(\d+)', ilk_3_satir, re.IGNORECASE)
        if fis_ilk_match:
            sonuc["belge_no"] = fis_ilk_match.group(1).strip()

    # Firma Adi (use original text not normalized so newlines preserved)
    sonuc["firma_adi"] = salon_bul(text)

    # Banka
    sonuc["banka_adi"] = banka_bul(t_duz) or ""

    # Brüt
    brut_patterns = [
        r'BR[UÜ]T[:\-]?\s*\d+\s*\*?\s*\+?\s*([\d][\d.,\sBOoIl]*[\d.,])',
        r'BR[UÜ]T\s*[:\-]?\s*\*?\s*([\d][\d.,\sBOoIl]*[\d.,])',
        r'BR[UÜ]T\s*[:\-]?\s*([\d,.BOoIl]+)',
        r'BR[UÜ]T\s*[:\-]?\s+\*?\+?\s*([\d][\d.,\sBOoIl]*[\d.,])',
        r'B\s*R\s*[UÜ]\s*T[:\-]?\s*([\d][\d.,\sBOoIl]*[\d.,])',
        r'B\s*R\s*[UÜ]\s*T[:\-]?\s*([\d,.BOoIl]+)',
        r'MAL[İI]\s*VER[İI][\s\S]{0,80}?TOPLAM\s*[:\-]?\s*\*?\s*([\d][\d.,\sBOoIl]*[\d.,])',
        r'BR[UÜ]T\s+\*?\s*([\d][\d.,\sBOoIl]*[\d.,])',
        r'MAL[İI]\s*VER[İI][\s\S]{0,100}?TOPLAM[:\s]*\*?\s*([\d][\d.,\s]{3,}[\d.,])',
    ]
    for pat in brut_patterns:
        m = re.search(pat, t_duz, re.IGNORECASE)
        if m:
            val_str = m.group(1).replace(" ", "")
            val = parse_tutar(val_str)
            if val > 0:
                sonuc["brut"] = val
                break

    if sonuc["brut"] == 0:
        mali_veri = re.search(r'MAL[İI]\s*VER[İI][\s\S]{0,200}?TOPLAM\s*\*?\s*([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE)
        if mali_veri:
            val_str = mali_veri.group(1).replace(" ", "")
            val = parse_tutar(val_str)
            if val > 0 and val < 100000:
                sonuc["brut"] = val

    # Z raporu: bagimsiz TOPLAM satiri (TOPLAM %1/%0/KDV olmayan)
    if sonuc["brut"] == 0:
        for m in re.finditer(r'TOPLAM\s*(?!%)\s*[:\-]?\s*\*?\s*([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE):
            val_str = m.group(1).replace(" ", "")
            val = parse_tutar(val_str)
            if val > 100 and val < 100000:
                sonuc["brut"] = val

    if sonuc["brut"] == 0:
        if sonuc["net_toplam"] > 0:
            sonuc["brut"] = sonuc["net_toplam"]
        elif sonuc["nakit"] + sonuc["kredi_karti"] + sonuc["yemek_ceki"] > 0:
            sonuc["brut"] = sonuc["nakit"] + sonuc["kredi_karti"] + sonuc["yemek_ceki"]

    if sonuc["brut"] == 0:
        genel_toplam = re.search(r'(?:NET\s*S?AT[İI]Ş|GENEL\s*TOPLAM)\s*\*?\s*([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE)
        if genel_toplam:
            val_str = genel_toplam.group(1).replace(" ", "")
            val = parse_tutar(val_str)
            if val > 0:
                sonuc["brut"] = val

    # Tum TOPLAM degerlerini topla, KDV olmayan en buyugunu Brut sec
    if sonuc["brut"] == 0:
        tum_toplam_eslesmeler = re.finditer(r'\bTOPLAM[^\n]{0,15}?\*?\s*([\d][\d.,\s]{3,}[\d.,])', t_duz, re.IGNORECASE)
        kdv_degerler = set()
        for kdv_pat in [r'TOPLAM\s*KDV[\s:]*\*?\s*([\d][\d.,\s]{3,}[\d.,])',
                        r'TOPK[DV][\s\w]*[:\s]*\*?\s*([\d][\d.,\s]{3,}[\d.,])',
                        r'KDV[\s:]+(?:TOPLAM|TUTAR)[\s:]*\*?\s*([\d][\d.,\s]{3,}[\d.,])',
                        r'TOPKDV[İI14l][\s:]*\*?\s*([\d][\d.,\s]{3,}[\d.,])']:
            for m in re.findall(kdv_pat, t_duz, re.IGNORECASE):
                v = parse_tutar(m.replace(" ", ""))
                if v > 0:
                    kdv_degerler.add(round(v, 2))
        adaylar = []
        for m in tum_toplam_eslesmeler:
            val_str = m.group(1)
            v = parse_tutar(val_str.replace(" ", ""))
            eslesen_text = m.group(0).upper()
            if v > 100 and v < 100000 and round(v, 2) not in kdv_degerler:
                if "KDV" in eslesen_text or "VERG" in eslesen_text:
                    continue
                # X0 ve X1 KDV matrahlari genelde daha kucuk (1k-20k araliginda)
                adaylar.append(v)
        if adaylar:
            sonuc["brut"] = max(adaylar)

    # TOPLAMI / TOPLAM4I / TOPLAM1 (Net deger) — "I" rakam olarak okunmus
    if sonuc["net_toplam"] == 0 or sonuc["net_toplam"] == sonuc["brut"]:
        net_toplami = re.search(r'TOPLAM[İI14l].{0,20}?([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE)
        if net_toplami:
            val = parse_tutar(net_toplami.group(1).replace(" ", ""))
            if val > 0 and val < 100000 and val != sonuc["brut"]:
                sonuc["net_toplam"] = val

    # K.KARTI sonraki deger (ocr_duzelt newlinelari kaldiriyor)
    if sonuc["kredi_karti"] < 100:
        kk_satir = re.search(r'K[\.\s]?KART[İIı]?\s+\d+\s+\.?\s*([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE)
        if kk_satir:
            val = parse_tutar(kk_satir.group(1).replace(" ", ""))
            if val > 100 and val < 100000:
                sonuc["kredi_karti"] = val

    # En buyuk TOPLAM (genellikle KDV-blok toplamlarindan buyuk olan)
    if sonuc["brut"] == 0 or sonuc["brut"] < 100:
        tum_toplamlar = re.findall(r'\bTOPLAM\b[\s\S]{0,30}?\*?\s*([\d][\d.,\sBOoIl]*[\d.,])', t_duz, re.IGNORECASE)
        en_buyuk = 0
        for tm in tum_toplamlar:
            v = parse_tutar(tm.replace(" ", ""))
            # YEKÜN/KÜM. değerleri genelde çok büyük, atla
            if v > 100000 or v < 100:
                continue
            if v > en_buyuk:
                en_buyuk = v
        if en_buyuk > sonuc["brut"] and en_buyuk > 100:
            sonuc["brut"] = en_buyuk

    if sonuc["brut"] == 0 and sonuc["nakit"] > 0:
        sonuc["brut"] = sonuc["nakit"]

    # Brut mantikli degilse (cok buyuk veya nakit+kk ile uyumsuz), nakit+kk yap
    if sonuc["brut"] > 100000 and (sonuc["nakit"] + sonuc["kredi_karti"]) > 0:
        beklenen = sonuc["nakit"] + sonuc["kredi_karti"] + sonuc["yemek_ceki"] + sonuc["iadeler"]
        if abs(sonuc["brut"] - beklenen) > 100000:
            sonuc["brut"] = beklenen

    # Net Ciro / Net Tutar
    net_pat = [
        r'NET\s*(?:C[İI]RO|TUTAR|TOPLAM|CIRO|SAT[İI]Ş)[:\-]?\s*\d+\s*\*?\s*\+?\s*([\d][\d.,\s]*[\d.,])',
        r'NET\s*(?:C[İI]RO|TUTAR|TOPLAM|CIRO|SAT[İI]Ş)[:\-]?\s*\*?\s*\+?\s*([\d][\d.,\s]*[\d.,])',
        r'NET\s*(?:C[İI]RO|TUTAR|TOPLAM|CIRO|SAT[İI]Ş)[:\-]?\s*([\d][\d.,\s]*[\d.,])',
        r'NET\s*(?:C[İI]RO|TUTAR|TOPLAM|CIRO|SAT[İI]Ş)[:\-]?\s*([\d,.]+)',
        r'Net\s*(?:Ciro|Tutar|Toplam|Sat[ıi][şs])[:\-]?\s*([\d,.]+)',
        r'NET\s+TUTAR[:\-]?\s*([\d,.]+)',
    ]
    for pat in net_pat:
        m = re.search(pat, t_duz, re.IGNORECASE)
        if m:
            val = parse_tutar(m.group(1).replace(" ", ""))
            if val > 0:
                sonuc["net_toplam"] = val
                break

    if sonuc["net_toplam"] == 0:
        brut_match = re.search(r'(?:BR[UÜ]T|NET\s*S?AT[İI]Ş|MAL[İI]\s*VER[İI]|TOPLAM)\s*[:\-]?\s*\*?\s*([\d][\d.,\sBOoIl]*[\d.,])', t_duz, re.IGNORECASE)
        if brut_match:
            val = parse_tutar(brut_match.group(1).replace(" ", ""))
            if val > 0 and val < 100000:
                sonuc["net_toplam"] = val

    # Net cok buyukse duzelt
    if sonuc["net_toplam"] > 100000 and sonuc["brut"] > 0 and sonuc["brut"] < 100000:
        sonuc["net_toplam"] = sonuc["brut"]

    if sonuc["net_toplam"] == 0 and sonuc["brut"] > 0:
        sonuc["net_toplam"] = sonuc["brut"]

    # KDV Kalemleri (parsedaki inline urun kdv kalemleri)
    kdv_blok_pat = r'KDV[:\-]?\s*(?:ORAN[İI]?|MATRAH)?[:\-]?\s*(\d+)[\s,.]*(\d+[.,]\d+)?'
    for m in re.finditer(kdv_blok_pat, t_duz, re.IGNORECASE):
        try:
            oran = int(m.group(1))
            if 0 < oran <= 90:
                tutar = parse_tutar(m.group(2)) if m.group(2) else 0
                sonuc["kdv_kalemleri"].append({"oran": oran, "matrah": 0, "kdv_tutari": tutar})
        except ValueError:
            log.warning("KDV blok parse hatasi", exc_info=True)

    # TOPLAM X1, X10, X20 KDV bloklari (Z raporu formatinda)
    # Ornek: "TOPLAM Zi *17. 864, 90" (Zi = Z1), "TOPKDV X1 *176, 91"
    kdv_x_pat = r'TOPLAM\s*([ZXz][Il1i]?[0O]?)\s*\*?\s*([\d][\d.,\s]*[\d.,])'
    for m in re.finditer(kdv_x_pat, t_duz, re.IGNORECASE):
        try:
            oran_str = m.group(1).upper().replace('Z', '2').replace('I', '1').replace('O', '0').replace('L', '1')
            oran_str = re.sub(r'[^0-9]', '', oran_str)
            if oran_str:
                oran = int(oran_str)
                if 0 < oran <= 90:
                    tutar = parse_tutar(m.group(2).replace(" ", ""))
                    if tutar > 0:
                        sonuc["kdv_kalemleri"].append({"oran": oran, "matrah": tutar, "kdv_tutari": 0})
        except (ValueError, IndexError):
            log.warning("TOPLAM X-kdv parse hatasi", exc_info=True)

    # TOPKDV X1, X10, X20 (KDV tutarlari)
    topkdv_x_pat = r'TOPKDV\s*[XZ]\s*([Il1iO0]{1,2})\s*\*?\s*([\d][\d.,\s]*[\d.,])'
    for m in re.finditer(topkdv_x_pat, t_duz, re.IGNORECASE):
        try:
            oran_str = m.group(1).replace('I', '1').replace('l', '1').replace('O', '0').replace('o', '0')
            oran = int(oran_str)
            if 0 < oran <= 90:
                tutar = parse_tutar(m.group(2).replace(" ", ""))
                if tutar > 0:
                    mevcut = next((k for k in sonuc["kdv_kalemleri"] if k.get("oran") == oran), None)
                    if mevcut:
                        mevcut["kdv_tutari"] = tutar
                    else:
                        sonuc["kdv_kalemleri"].append({"oran": oran, "matrah": 0, "kdv_tutari": tutar})
        except (ValueError, IndexError):
            log.warning("TOPKDV X-kdv parse hatasi", exc_info=True)

    # Ürün satırları (hem satir satir hem tek satirdan parse)
    satir_liste = t_duz.replace('\r', '\n').split("\n")
    skip_urunler = re.compile(
        r'^(URUN|MALZEME|SIRA|TOPLAM|ARA|MAHSUP|KDV|NAK[İI]?T|K\.?\s*KART|F[İI][ŞS]?\s*[İI]PTAL|GE[CÇ]ERL[İI]|MAL[İI]\s*F[İI][ŞS]|SL[İI]P|TOPLAM\s*F[İI][ŞS]|VERG[İI]|M[ÜU]ŞTER[İI]|M[ÜU]KELLEF|TAR[İI]H|SAAT|EK[ÜU]|BELGE|Z\s*NO|Z\s*SAYA[CÇ]|TOPKDV|AT\s+\d+|F[İI]Ş|ISYER[İI]|TER[İI]M[İI]NAL|TC\s*NO|VKN|TOPLAR|TUTAR|TOPKDV|KUM|M[ÜU]KELLEF)',
        re.IGNORECASE
    )
    if len(satir_liste) <= 1:
        # Tek satırsa, urun pattern'i için findall kullan
        urun_pat_inline = r'([A-ZÇĞIİÖŞÜa-zçğıöşü][A-ZÇĞIİÖŞÜa-zçğıöşü\s\.\-]{2,30}?)\s+%?(\d{1,2})?\s*(\d+[.,]?\d*)\s+\*?\s*([\d][\d.,\sBOoIl]*[\d.,BOoIl])'
        for m in re.finditer(urun_pat_inline, t_duz):
            ad = m.group(1).strip()
            if skip_urunler.match(ad):
                continue
            if len(ad) < 2 or ad.isdigit():
                continue
            kdv_orani = 0
            try:
                kdv_orani = int(m.group(2)) if m.group(2) else 0
            except (ValueError, TypeError):
                pass
            miktar = parse_tutar(m.group(3))
            tutar = parse_tutar(m.group(4).replace(" ", ""))
            if tutar > 0 and len(ad) > 1 and not ad.isdigit() and tutar < 10000000:
                sonuc["urunler"].append({
                    "urun": ad, "miktar": miktar,
                    "birim_fiyat": 0, "tutar": tutar,
                    "oran": kdv_orani,
                })
    else:
        for satir in satir_liste:
            satir = satir.strip()
            if not satir or len(satir) < 5:
                continue
            if skip_urunler.match(satir):
                continue
            urun_pat = r'^(.+?)\s+%?(\d{1,2})?\s*(\d+[.,]?\d*)\s+\*?\s*([\d][\d.,\sBOoIl]*[\d.,BOoIl])$'
            m = re.match(urun_pat, satir)
            if m:
                ad = m.group(1).strip()
                kdv_orani = int(m.group(2)) if m.group(2) else 0
                miktar = parse_tutar(m.group(3))
                tutar = parse_tutar(m.group(4).replace(" ", ""))
                if tutar > 0 and len(ad) > 1 and not ad.isdigit() and tutar < 10000000:
                    sonuc["urunler"].append({
                        "urun": ad, "miktar": miktar,
                        "birim_fiyat": 0, "tutar": tutar,
                        "oran": kdv_orani,
                    })
                    continue
            urun_pat2 = r'^(.+?)\s+(\d+[.,]?\d*)\s+\*?\s*([\d][\d.,\sBOoIl]*[\d.,BOoIl])$'
            m = re.match(urun_pat2, satir)
            if m:
                ad = m.group(1).strip()
                miktar = parse_tutar(m.group(2))
                tutar = parse_tutar(m.group(3).replace(" ", ""))
                if tutar > 0 and len(ad) > 1 and not ad.isdigit() and tutar < 10000000:
                    sonuc["urunler"].append({
                        "urun": ad, "miktar": miktar,
                        "birim_fiyat": 0, "tutar": tutar,
                        "oran": 0,
                    })

    # Tahsilat TOPLAM
    tahsilat_pat = [
        r'TOPLAM\s*TAHS[İI]LAT[:\-]?\s*\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        r'TOPLAM\s*TAHS[İI]LAT[:\-]?\s*([\d][\d.,\s]*[\d.,])',
        r'TOPLAM\s*TAHS[İI]LAT[:\-]?\s*([\d,.]+)',
        r'TAHS[İI]LAT\s*TOPLAM[İI]?\s*[:\-]?\s*([\d][\d.,\s]*[\d.,])',
    ]
    for pat in tahsilat_pat:
        m = re.search(pat, t_duz, re.IGNORECASE)
        if m:
            val = parse_tutar(m.group(1).replace(" ", ""))
            if val > 0:
                sonuc["toplam_tahsilat"] = val
                break

    if sonuc["toplam_tahsilat"] == 0:
        if sonuc["brut"] > 0:
            sonuc["toplam_tahsilat"] = sonuc["brut"]
        elif sonuc["net_toplam"] > 0:
            sonuc["toplam_tahsilat"] = sonuc["net_toplam"]
        elif sonuc["nakit"] + sonuc["kredi_karti"] + sonuc["yemek_ceki"] > 0:
            sonuc["toplam_tahsilat"] = sonuc["nakit"] + sonuc["kredi_karti"] + sonuc["yemek_ceki"]

    # Nakit - non-count patterns first to handle spaced numbers
    nakit_patterns = [
        r'NAK[İiI]?T\s*[:\-]?\s+\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        r'NAKIT\s*[:\-]?\s+\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        r'[Nn]akit\s*[:\-]?\s+\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        r'NAK[İiI]?T\s*[:\-]?\s*\d+\s+[\dxX\*\+\-]*\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'NAKIT\s*[:\-]?\s*\d+\s+[\dxX\*\+\-]*\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'KASA\s*NAK[İiI]?T[\s\S]{0,40}?\*?\s*([\d][\d.,\s]*[\d.,])',
        r'KASA\s*NAKIT[\s\S]{0,40}?\*?\s*([\d][\d.,\s]*[\d.,])',
        r'NAK[İiI]?T\s*VE\s*NAK[İiI]?T\s*[\s\S]{0,40}?\*?\s*([\d][\d.,\s]*[\d.,])',
        r'NAK[İiI]?T\s*[:\-]?\s+\d+\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'NAK[İiI]?T\s*[:\-]?\s+\d+[.,]?\d*\s*[\dxX\*]?\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        # NAKT + deger (ocr_duzelt newlinelari kaldiriyor, boslukla ayrilmis)
        r'NAK[İiI]?T\s+\d+\s+[:\*]?\s*([\d][\d.,\s]*[\d.,])',
        r'NAK[İiI]?T\s+\d+\s+\.?([\d][\d.,]{3,}[\d.,])',
        # KASA NAKIT deger sonraki satirda (boslukla ayrilmis)
        r'KASA\s*NAK[İiI]?T[\s\S]{0,30}?([\d][\d.,\s]{3,}[\d.,])',
        # HAKIT (OCR hata NAKIT -> HAKIT)
        r'HAK[İiI]?T[\s\S]{0,30}?([\d][\d.,\s]{3,}[\d.,])',
    ]
    for pat in nakit_patterns:
        m = re.search(pat, t_duz, re.IGNORECASE)
        if m:
            tutar_str = m.group(1).replace(" ", "")
            if "," not in tutar_str and "." not in tutar_str:
                continue
            val = parse_tutar(tutar_str)
            if val > 0:
                sonuc["nakit"] = val
                break

    if sonuc["nakit"] == 0:
        nakit_satiri = re.search(r'NAK[İiI]?T[^\d\-]{0,15}-?[\d\s\w]{0,15}?[\dxX\*]?\s*([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE)
        if nakit_satiri:
            val_str = nakit_satiri.group(1).replace(" ", "")
            if "," in val_str or "." in val_str:
                val = parse_tutar(val_str)
                if val > 0:
                    sonuc["nakit"] = val

    if sonuc["nakit"] == 0:
        nakit_fallback = re.search(r'NAK[İiI]?T[\s\S]{0,30}?[\dxX\*]?\s*([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE)
        if nakit_fallback:
            val_str = nakit_fallback.group(1).replace(" ", "")
            if "," in val_str or "." in val_str:
                val = parse_tutar(val_str)
                if val > 0:
                    sonuc["nakit"] = val

    if sonuc["nakit"] == 0 and sonuc["kredi_karti"] == 0:
        odeme_blok = re.search(r'[ÖO]DEME\s*T[ÜU]RLER[İI][\s\S]{0,400}', t_duz, re.IGNORECASE)
        if odeme_blok:
            blok = odeme_blok.group(0)
            nakit_match = re.search(r'^\s*NAK[İiI]T?\s*[\s\S]{0,40}?\*?\s*([\d][\d.,]*[\d.,])', blok, re.IGNORECASE | re.MULTILINE)
            if nakit_match:
                val = parse_tutar(nakit_match.group(1).replace(" ", ""))
                if val > 0:
                    sonuc["nakit"] = val

    # Kredi Kartı
    kart_patterns = [
        # K. KARTI <count> [-] [*4] <amount> - OCR * isaretini 4 olarak okuyabilir, - isareti olabilir
        r'K[\.\s]\s*KART[İIı]?\s+\d+\s*\-?\s*[\d]?\s*([\d][\d.,\s]*[\d.,])',
        r'KRED[İI]?\s*KART[İIı]?\s+\d+\s*\-?\s*[\d]?\s*([\d][\d.,\s]*[\d.,])',
        r'BANKA\s*[/\-]?\s*KART[İIı]?\s+\d+\s*\-?\s*[\d]?\s*([\d][\d.,\s]*[\d.,])',
        r'BANKA\s*[/\-]?\s*KRED[İI]?\s*KART[İIı]?\s+\d+\s*\-?\s*[\d]?\s*([\d][\d.,\s]*[\d.,])',
        # K. KARTI <count> *<amount> - Z raporu formatinda sayiyi atla (en guvenilir pattern)
        r'K[\.\s]\s*KART[İIı]?\s+\d+\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'KRED[İI]?\s*KART[İIı]?[:\-]?\s*\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        r'BANKA\s*[/\-]?\s*KART[İIı]?[:\-]?\s*\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        r'BANKA\s*[/\-]?\s*KRED[İI]?\s*KART[İIı]?[:\-/]?\s*\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        # K. KARTI <count> [-] *<amount> - Z raporu formatinda sayiyi atla
        r'K[\.\s]\s*KART[İIı]?[\s\S]{0,20}?\*\s*([\d][\d.,\s]*[\d.,])',
        r'KRED[İI]?\s*KART[İIı]?[\s\S]{0,20}?\*\s*([\d][\d.,\s]*[\d.,])',
        r'BANKA\s*[/\-]?\s*KART[İIı]?[\s\S]{0,20}?\*\s*([\d][\d.,\s]*[\d.,])',
        r'BANKA\s*[/\-]?\s*KRED[İI]?\s*KART[İIı]?[\s\S]{0,20}?\*\s*([\d][\d.,\s]*[\d.,])',
        r'K\s*[\.\s]?\s*KART[İIı]?[\s\S]{0,20}?\*\s*([\d][\d.,\s]*[\d.,])',
        # K. KARTI <count> *<amount> - Z raporu formatinda sayiyi atla (eski pattern, hala calisiyor)
        r'KRED[İI]?\s*KART[İIı]?[:\-]?\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'KRED[İI]?\s*KART[İIı]?[:\-]?\s+([\d,.]+)',
        r'BANKA\s*KART[İIı]?\s*[İIı]*LE[:\-]?\s*\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        r'BANKA\s*KART[İIı]?\s*[İIı]*LE[:\-]?\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'Kredi\s*Kart[ıi]?[:\-]?\s*([\d,.]+)',
        r'Banka\s*Kart[ıi]?\s*[ıi]?le[:\-]?\s*([\d,.]+)',
        r'BANKA\s*[/\-]?\s*KRED[İI]?\s*KART[İIı]?[:\-/]?\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'BANKA\s*[/\-]\s*KART[İIı]?[:\-/]?\s*\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        r'KASA\s*Nakit[\s\S]{0,40}?BANKA\s*[/\-]?\s*KART[İIı]?[:\-/]?\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'POS\s*CIRO\s*VE\s*TAHS[İI]LAT[\s\S]{0,80}?BANKA\s*[/\-]?\s*KART[İIı]?[:\-/]?\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'[İI][ŞS]\s*Bankas[ıi][:\-]?\s*\d{0,2}\s*[\w\s\-\*\.\/]*?\*?\s*([\d][\d.,\s]*[\d.,])',
        r'Is\s*Bankas[ıi]\s*\d{0,2}\s*[\w\s\-\*\.\/]*?\*?\s*([\d][\d.,\s]*[\d.,])',
        r'Banka\s*POS[\s\S]{0,30}?\*?\s*([\d][\d.,\s]*[\d.,])',
        r'K\s*[\.\s]?\s*KART[İIı]?[\s:]\s*\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        r'K\s*[\.\s]\s*KART[İIı]?[\s:]\s*[\w\s\-\*\.\/]*?\*?\s*([\d][\d.,\s]*[\d.,])',
    ]
    for pat in kart_patterns:
        m = re.search(pat, t_duz, re.IGNORECASE)
        if m:
            val_str = m.group(1).replace(" ", "")
            if "," not in val_str and "." not in val_str:
                continue
            val = parse_tutar(val_str)
            if val > 0:
                sonuc["kredi_karti"] = val
                break

    if sonuc["kredi_karti"] == 0:
        kk_satiri = re.search(r'K[\.\s]?KART[İIı][\s\S]{0,60}?\*?\s*([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE)
        if kk_satiri:
            val_str = kk_satiri.group(1).replace(" ", "")
            if "," in val_str or "." in val_str:
                val = parse_tutar(val_str)
                if val > 50 and val > sonuc["kredi_karti"]:
                    sonuc["kredi_karti"] = val

    if sonuc["kredi_karti"] == 0:
        banka_satiri = re.search(r'[İI][ŞS]\s*BANKAS[İI][\s\S]{0,40}?\*?\s*([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE)
        if banka_satiri:
            val_str = banka_satiri.group(1).replace(" ", "")
            if "," in val_str or "." in val_str:
                val = parse_tutar(val_str)
                if val > 50 and val > sonuc["kredi_karti"]:
                    sonuc["kredi_karti"] = val

    if sonuc["kredi_karti"] == 0:
        kart_fallback = re.search(r'K\.?\s*KART[İIı]?[\s\S]{0,30}?[\dxX\*\-\.\s]*?\*?\s*([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE)
        if kart_fallback:
            val_str = kart_fallback.group(1).replace(" ", "")
            if "," in val_str or "." in val_str:
                val = parse_tutar(val_str)
                if val > 50 and val > sonuc["kredi_karti"]:
                    sonuc["kredi_karti"] = val

    # KART sonrasi * tutar (son care)
    if sonuc["kredi_karti"] == 0 or sonuc["kredi_karti"] < 100:
        kart_yakin = re.search(r'KART[IiıIİ][\s\S]{0,80}?\*\s*([\d][\d.,\s]*[\d.,])', t_duz, re.IGNORECASE)
        if kart_yakin:
            val_str = kart_yakin.group(1).replace(" ", "")
            if "," in val_str or "." in val_str:
                val = parse_tutar(val_str)
                if val > 50 and val > sonuc["kredi_karti"]:
                    sonuc["kredi_karti"] = val

    if sonuc["kredi_karti"] == 0:
        odeme_blok = re.search(r'[ÖO]DEME\s*T[ÜU]RLER[İI][\s\S]{0,400}', t_duz, re.IGNORECASE)
        if odeme_blok:
            blok = odeme_blok.group(0)
            kk_match = re.search(r'BANKA\s*[/\-]?\s*KRED[İI]?\s*KART[İIı]?[\s\S]{0,80}?\*?\s*([\d][\d.,]*[\d.,])', blok, re.IGNORECASE)
            if kk_match:
                val = parse_tutar(kk_match.group(1).replace(" ", ""))
                if val > 0:
                    sonuc["kredi_karti"] = val

    # Yemek Çeki
    yemek_patterns = [
        r'YEMEK\s*[ÇC]EK[İI][:\-]?\s*\d+\s+\*?\+?\s*([\d][\d.,\s]*[\d.,])',
        r'YEMEK\s*[ÇC]EK[İI][:\-]?\s*\*?\s*\+?\s*([\d][\d.,\s]*[\d.,])',
        r'YEMEK\s*[ÇC]EK[İI][:\-]?\s*([\d][\d.,\s]*[\d.,])',
        r'YEMEK\s*[ÇC]EK[İI][:\-]?\s+([\d,.]+)',
        r'Yemek\s*[ÇC]ek[ıi][:\-]?\s*\d+\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'Yemek\s*[ÇC]ek[ıi][:\-]?\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'Yemek\s*[ÇC]ek[ıi][:\-]?\s*([\d,.]+)',
        r'YEMEK\s*[ÇC]EK[İI][\s/][Kk][Aa][Rr][Tt][İIı][:\-/]?\s*\d*\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'Yemek\s*[ÇC]ek[ıi][\s/][Kk][Aa][Rr][Tt][ıiı][:\-/]?\s*\d*\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'TICKET\s*RESTAURANT[:\-]?\s*\d*\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'MULTINET[:\-]?\s*\d*\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'SODEXO[:\-]?\s*\d*\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'SETCARD[:\-]?\s*\d*\s*\*?\s*([\d][\d.,\s]*[\d.,])',
    ]
    for pat in yemek_patterns:
        m = re.search(pat, t_duz, re.IGNORECASE)
        if m:
            val = parse_tutar(m.group(1).replace(" ", ""))
            if val > 0:
                sonuc["yemek_ceki"] = val
                break

    # İadeler (Fiş İptal = İade)
    iade_patterns = [
        # FİŞ İPTAL <count> <amount> - basit format, count ve tutar arasinda sadece bosluk
        r'(?:F[İIŞ]S?\s*)?[İI]PTAL\s+\d+\s+([\d][\d.,\s]*[\d.,])',
        # FİŞ İPTAL <count> [-] *<amount> - count ve - isareti sonrasi * ile baslayan tutar
        r'(?:F[İIŞ]S?\s*)?[İI]PTAL\s+\d+\s*\-?\s*\*\s*([\d][\d.,\s]*[\d.,])',
        # FİŞ İPTAL <count> [-] [*4] <amount> - OCR * isaretini 4 olarak okuyabilir
        r'(?:F[İIŞ]S?\s*)?[İI]PTAL\s+\d+\s*\-?\s*[\*4]\s*([\d][\d.,\s]*[\d.,])',
        # FİŞ İPTAL <count> *<amount> - Z raporu formatinda sayiyi atla (en guvenilir pattern)
        r'(?:F[İIŞ]S?\s*)?[İI]PTAL\s+\d+\s+\*?\s*([\d][\d.,\s]*[\d.,])',
        r'F[İI]S\s*[İI]PTAL\s+\d+\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'[İI]PTAL\s+\d+\s*\*?\s*([\d][\d.,\s]*[\d.,])',
        r'(?:FIS|FİS)\s*(?:IPTAL|İPTAL)\s+\d+\s+\*?\s*([\d.,]+)',
        # FİŞ İPTAL <count> [-] *<amount> - Z raporu formatinda sayiyi atla (count ve - isareti sonrasi * ile baslayan tutar)
        r'(?:F[İIŞ]S?\s*)?[İI]PTAL[\s\S]{0,20}?\*\s*([\d][\d.,\s]*[\d.,])',
        # İPTAL * amount (count yok veya onceden okundu)
        r'(?:F[İIŞ]S?\s*)?[İI]PTAL[:\-]?\s*\*?\s*\+?\s*([\d][\d.,\s]*[\d.,])',
        r'(?:F[İIŞ]S?\s*)?[İI]PTAL[:\-]?\s*([\d][\d.,\s]*[\d.,])',
        r'(?:F[İIŞ]S?\s*)?[İI]PTAL[:\-]?\s+([\d,.]+)',
        r'[İI]ADE[:\-]?\s*\d+\s+\*?\+?\s*([\d][\d.,\s]*[\d.,])',
        r'[İI]ADE[:\-]?\s*\*?\s*\+?\s*([\d][\d.,\s]*[\d.,])',
        r'[İI]ADE[:\-]?\s*([\d][\d.,\s]*[\d.,])',
        r'[İI]adeler?[:\-]?\s*([\d,.]+)',
        r'F[İI]S\s*[İI]PTAL[:\-]?\s*\d+\s+\*?\+?\s*([\d][\d.,\s]*[\d.,])',
        r'F[İI]S\s*[İI]PTAL[:\-]?\s*\*?\s*\+?\s*([\d][\d.,\s]*[\d.,])',
        r'F[İI]S\s*[İI]PTAL[:\-]?\s*([\d][\d.,\s]*[\d.,])',
        # FIS IPTAL + deger (ocr_duzelt newlinelari kaldiriyor)
        r'(?:F[İIŞ]S?\s*)?[İI]PTAL[\s\S]{0,40}?([\d][\d.,\s]{3,}[\d.,])',
    ]
    for pat in iade_patterns:
        m = re.search(pat, t_duz, re.IGNORECASE)
        if m:
            val = parse_tutar(m.group(1).replace(" ", ""))
            if val >= 10 and val < 100000:
                # OCR "1955" -> "11955" hata duzeltme
                if val > 10000 and val < 20000:
                    val_alt = float(str(val)[1:])
                    if val_alt > 100 and val_alt < 10000:
                        toplam_odeme = sonuc["nakit"] + sonuc["kredi_karti"] + sonuc["yemek_ceki"]
                        fark = sonuc["brut"] - toplam_odeme
                        if abs(fark - val_alt) < abs(fark - val):
                            val = val_alt
                sonuc["iadeler"] = val
                break

    # Capraz dogrulama: brut ≈ nakit + kk + yemek - iade
    if sonuc["brut"] > 0:
        toplam_odeme = sonuc["nakit"] + sonuc["kredi_karti"] + sonuc["yemek_ceki"]
        if toplam_odeme > 0:
            fark = sonuc["brut"] - toplam_odeme
            if 0 < fark < 100 and sonuc["iadeler"] == 0:
                sonuc["iadeler"] = fark

    # OCR hata duzeltme: KK veya Iade degeri brut'tan cok kucukse (muhtemelen count okundu)
    if sonuc["brut"] > 0:
        if sonuc["kredi_karti"] > 0 and sonuc["kredi_karti"] < 100 and sonuc["brut"] > 1000:
            brut_fark = sonuc["brut"] - sonuc["nakit"] - sonuc["yemek_ceki"] - sonuc["iadeler"]
            if brut_fark > 100:
                sonuc["kredi_karti"] = brut_fark
        if sonuc["iadeler"] > 0 and sonuc["iadeler"] < 100 and sonuc["brut"] > 1000:
            toplam_odeme = sonuc["nakit"] + sonuc["kredi_karti"] + sonuc["yemek_ceki"]
            beklenen_iade = toplam_odeme - sonuc["brut"]
            if beklenen_iade > 100 and beklenen_iade < sonuc["brut"]:
                sonuc["iadeler"] = beklenen_iade

    # Net toplam duzeltme: brut ve urunlerden net hesapla
    if sonuc["brut"] > 0 and sonuc["net_toplam"] >= sonuc["brut"] and sonuc.get("urunler"):
        urun_toplam = sum((u.get("tutar", 0) or 0) for u in sonuc["urunler"])
        if urun_toplam > 0 and urun_toplam < sonuc["brut"]:
            sonuc["net_toplam"] = urun_toplam
        elif urun_toplam > 0:
            # Urunlerin KDV oranlarindan net toplami hesapla
            hesaplanan_net = 0.0
            for u in sonuc["urunler"]:
                tutar = u.get("tutar", 0) or 0
                oran = u.get("oran", 0) or 0
                if oran > 0:
                    hesaplanan_net += round(tutar / (1 + oran / 100), 2)
                else:
                    hesaplanan_net += tutar
            if 0 < hesaplanan_net < sonuc["brut"]:
                sonuc["net_toplam"] = round(hesaplanan_net, 2)
            else:
                sonuc["net_toplam"] = sonuc["brut"] * 0.83
        elif urun_toplam == 0:
            sonuc["net_toplam"] = sonuc["brut"] * 0.83

    return sonuc
