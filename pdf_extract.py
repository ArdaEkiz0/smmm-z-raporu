"""
PDF text extraction + OCR fallback.
Termal yazici ciktilarinda (Z raporlari) zaten text var.
Once metni cikar, kaliteli ise direkt parse et; yoksa OCR'a dus.
"""
from typing import Tuple, List, Optional
from utils import log


def pdf_sayfalarini_ayir(pdf_bytes: bytes) -> List[bytes]:
    """PDF'i sayfa bazinda ayir, her sayfa icin bytes don.
    Returns: [page1_bytes, page2_bytes, ...]
    """
    try:
        import pypdf
        from io import BytesIO

        reader = pypdf.PdfReader(BytesIO(pdf_bytes))
        sayfalar = []
        for sayfa in reader.pages:
            writer = pypdf.PdfWriter()
            writer.add_page(sayfa)
            buf = BytesIO()
            writer.write(buf)
            sayfalar.append(buf.getvalue())
        return sayfalar
    except Exception:
        log.warning("PDF sayfa ayirma basarisiz", exc_info=True)
        return []


def pdf_text_cikar(pdf_bytes: bytes) -> Tuple[str, float]:
    """PDF'ten text cikar. (text, kalite_skoru) doner.
    kalite_skoru 0-100, yuksek = temiz metin.
    """
    try:
        import pypdf
        from io import BytesIO

        reader = pypdf.PdfReader(BytesIO(pdf_bytes))
        tum_text = ""
        for sayfa in reader.pages:
            try:
                tum_text += sayfa.extract_text() + "\n"
            except Exception:
                log.warning("PDF sayfa text cikarma basarisiz", exc_info=True)
                continue

        if not tum_text.strip():
            return "", 0.0

        kalite = _pdf_kalite_skorla(tum_text)
        return tum_text, kalite
    except Exception:
        log.warning("PDF text cikarma basarisiz", exc_info=True)
        return "", 0.0


def _pdf_kalite_skorla(text: str) -> float:
    """PDF text kalitesini puanla (0-100).
    Temiz dijital text yuksek puan alir.
    Bozuk, eksik veya OCR-gerekli text dusuk puan alir.
    """
    if not text or len(text) < 20:
        return 0.0

    skor = 50.0
    satir_sayisi = len(text.strip().split("\n"))

    uzun_satir = sum(1 for s in text.split("\n") if len(s.strip()) > 15)
    if satir_sayisi > 0 and uzun_satir / max(satir_sayisi, 1) > 0.5:
        skor += 20

    keywords = ["Z RAPORU", "BRUT", "BRÜT", "NET", "TOPLAM", "NAKIT", "NAKİT", "KREDI", "KREDİ",
                "KDV", "CIRO", "CİRO", "TUTAR", "TARIH", "TARİH", "FIS", "FİŞ", "VKN", "TCKN", "ŞUBE", "FİRMA"]
    ust = text.upper()
    hit = sum(1 for k in keywords if k in ust)
    skor += min(hit * 4, 30)

    import re
    tutar_var = bool(re.search(r"\d+[.,]\d{2}", text))
    tarih_var = bool(re.search(r"\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}", text))
    if tutar_var:
        skor += 10
    if tarih_var:
        skor += 10

    if "�" in text or len(re.findall(r"[^\x00-\x7F\u00C0-\u017F\u011E\u015E\u00DC\u00D6\u00C7]", text)) > 5:
        skor -= 20

    return max(0.0, min(100.0, skor))


def pdf_text_yeterli_mi(kalite: float, esik: float = 60.0) -> bool:
    """Text kalitesi yeterli mi yoksa OCR gerekli mi?"""
    return kalite >= esik


def pdf_sayfa_sayisi(pdf_bytes: bytes) -> int:
    try:
        import pypdf
        from io import BytesIO
        reader = pypdf.PdfReader(BytesIO(pdf_bytes))
        return len(reader.pages)
    except Exception:
        log.warning("PDF sayfa sayisi alinamadi", exc_info=True)
        return 0
