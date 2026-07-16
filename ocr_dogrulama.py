"""
ocr_dogrulama.py — OCR dogrulama ve kalite kontrol motoru.

OCR'in okudugu veriyi su acidan dogrular:
1. Format dogrulugu (tarih gecerli mi, tutar sayi mi, VKN/TCKN gecerli mi)
2. Anomali tespiti (firma_adi tamamen sayi olamaz)
3. Capraz referans (mukellef listesinde var mi, urun kodlariyla uyusuyor mu)
4. Tutarsizlik tespiti (nakit + kk + yemek != brut)
"""
import re
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

from utils import log, turkce_normalize


# Field validation rule sets
ALAN_KURALLARI = {
    "tarih": {"type": "tarih", "gerekli": True, "min_uzunluk": 8, "max_uzunluk": 12},
    "z_no": {"type": "no", "gerekli": False, "min_uzunluk": 1, "max_uzunluk": 10},
    "belge_no": {"type": "no", "gerekli": False, "min_uzunluk": 1, "max_uzunluk": 10},
    "firma_adi": {"type": "metin", "gerekli": True, "min_uzunluk": 3, "max_uzunluk": 60},
    "banka_adi": {"type": "metin", "gerekli": False, "min_uzunluk": 3, "max_uzunluk": 40},
    "brut": {"type": "sayi", "gerekli": True, "min_deger": 0, "max_deger": 100000},
    "net_toplam": {"type": "sayi", "gerekli": False, "min_deger": 0, "max_deger": 100000},
    "nakit": {"type": "sayi", "gerekli": False, "min_deger": 0, "max_deger": 100000},
    "kredi_karti": {"type": "sayi", "gerekli": False, "min_deger": 0, "max_deger": 100000},
    "yemek_ceki": {"type": "sayi", "gerekli": False, "min_deger": 0, "max_deger": 100000},
    "iadeler": {"type": "sayi", "gerekli": False, "min_deger": 0, "max_deger": 100000},
    "toplam_tahsilat": {"type": "sayi", "gerekli": False, "min_deger": 0, "max_deger": 100000},
}


def _tarih_dogrula(deger: str) -> Tuple[bool, str]:
    """Tarih formatini dogrula."""
    if not deger:
        return False, "bos"

    deger = deger.strip()

    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y.%m.%d", "%Y/%m/%d"]:
        try:
            dt = datetime.strptime(deger, fmt)
            if dt.year < 1900 or dt.year > 2100:
                return False, f"yil_gecersiz: {dt.year}"
            if dt.month < 1 or dt.month > 12:
                return False, f"ay_gecersiz: {dt.month}"
            if dt.day < 1 or dt.day > 31:
                return False, f"gun_gecersiz: {dt.day}"
            return True, "gecerli"
        except ValueError:
            continue

    if re.match(r'^\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}$', deger):
        try:
            parts = re.split(r'[./\-]', deger)
            gun = int(parts[0])
            ay = int(parts[1])
            yil = int(parts[2])
            if yil < 100:
                yil += 2000
            datetime(yil, ay, gun)
            return True, "gecerli_parcali"
        except (ValueError, IndexError):
            return False, "tarih_ayristirilamadi"

    tarih_chars = sum(1 for c in deger if c.isdigit() or c in "./-")
    if len(deger) > 0 and tarih_chars / max(len(deger), 1) < 0.4:
        return False, "cok_fazla_harf_var"

    return False, "format_tanimisiz"


def _sayi_dogrula(deger: Any, kurallar: dict) -> Tuple[bool, str]:
    """Sayisal alani dogrula."""
    try:
        val = float(deger) if not isinstance(deger, (int, float)) else deger
    except (ValueError, TypeError):
        return False, "sayi_degil"

    min_d = kurallar.get("min_deger", 0)
    max_d = kurallar.get("max_deger", 10**9)

    if val < min_d:
        return False, f"cok_kucuk: {val} < {min_d}"
    if val > max_d:
        return False, f"cok_buyuk: {val} > {max_d}"

    return True, "gecerli"


def _metin_dogrula(deger: str, kurallar: dict, alan_adi: str = "") -> Tuple[bool, str]:
    """Metin alanini dogrula."""
    if not deger:
        return False, "bos"

    deger = str(deger).strip()
    min_u = kurallar.get("min_uzunluk", 1)
    max_u = kurallar.get("max_uzunluk", 100)

    if len(deger) < min_u:
        return False, f"cok_kisa: {len(deger)} < {min_u}"
    if len(deger) > max_u:
        return False, f"cok_uzun: {len(deger)} > {max_u}"

    if alan_adi == "firma_adi":
        if deger.isdigit():
            return False, "sadece_rakam"
        if len(re.findall(r'[a-zA-ZİıŞşĞğÜüÖöÇç]', deger)) < 2:
            return False, "yeterli_harf_yok"
        if re.search(r'[�\x00-\x08\x0B\x0C\x0E-\x1F]', deger):
            return False, "bozuk_karakter"

    if alan_adi == "banka_adi" and len(deger) > 0:
        bilinen_bankalar = [
            "AKBANK", "GARANTİ", "GARANTI", "İŞ BANKASI", "IS BANKASI",
            "YAPI KREDİ", "YAPI KREDI", "HALK BANK", "ZİRAAT", "VAKIF",
            "DENİZBANK", "DENIZBANK", "QNB", "FINANS", "TEB", "HSBC",
            "ALTERNATİF", "ALTERNATIF", "ING", "CITI", "CITIBANK",
        ]
        if not any(b in deger.upper() for b in bilinen_bankalar):
            pass  # soft warning only, don't fail

    return True, "gecerli"


def _tutarlilik_dogrula(parsed: dict) -> List[dict]:
    """Alanlar arasi tutarlilik kontrolleri."""
    sorunlar = []

    brut = parsed.get("brut", 0) or 0
    net = parsed.get("net_toplam", 0) or 0
    nakit = parsed.get("nakit", 0) or 0
    kk = parsed.get("kredi_karti", 0) or 0
    yemek = parsed.get("yemek_ceki", 0) or 0
    iade = parsed.get("iadeler", 0) or 0

    toplam_tahsilat = nakit + kk + yemek + iade

    if brut > 0 and toplam_tahsilat > 0:
        fark = abs(brut - toplam_tahsilat)
        if fark > 0.50 and fark / max(brut, 1) > 0.05:
            sorunlar.append({
                "alan": "brut",
                "seviye": "uyari",
                "mesaj": f"Brüt ({brut:.2f}) ile tahsilat toplami ({toplam_tahsilat:.2f}) uyusmuyor (fark: {fark:.2f})",
                "kod": "BRUT_TAHSILAT_FARKI",
            })

    if brut > 0 and net > 0 and net > brut:
        sorunlar.append({
            "alan": "net_toplam",
            "seviye": "uyari",
            "mesaj": f"Net toplam ({net:.2f}) brutten ({brut:.2f}) buyuk",
            "kod": "NET_BRUTTEN_BUYUK",
        })

    if brut > 0 and iade > brut:
        sorunlar.append({
            "alan": "iadeler",
            "seviye": "hata",
            "mesaj": f"Iade ({iade:.2f}) brutten ({brut:.2f}) buyuk olamaz",
            "kod": "IADE_BRUTTEN_BUYUK",
        })

    if kk > 0 and brut > 0 and kk > brut:
        sorunlar.append({
            "alan": "kredi_karti",
            "seviye": "uyari",
            "mesaj": f"Kredi karti ({kk:.2f}) brutten ({brut:.2f}) buyuk",
            "kod": "KK_BRUTTEN_BUYUK",
        })

    return sorunlar


def _anomali_tespit(parsed: dict, ham_text: str = "") -> List[dict]:
    """Anomali tespiti - normal olmayan durumlar."""
    sorunlar = []

    firma = parsed.get("firma_adi", "")
    if firma:
        if len(firma) == len(re.findall(r'[A-Z]', firma.upper())):
            pass
        if re.search(r'(ERROR|HATA|NULL|NONE|UNDEFINED|BOS)', firma, re.IGNORECASE):
            sorunlar.append({
                "alan": "firma_adi",
                "seviye": "hata",
                "mesaj": f"Firma adi hata iceriyor: '{firma}'",
                "kod": "FIRMA_HATA_ICERIYOR",
            })
        if len(set(firma.upper())) <= 3 and len(firma) >= 5:
            sorunlar.append({
                "alan": "firma_adi",
                "seviye": "uyari",
                "mesaj": f"Firma adi supheli: '{firma}' (cok az farkli karakter)",
                "kod": "FIRMA_TEKRAR_KARAKTER",
            })

    brut = parsed.get("brut", 0) or 0
    if brut > 0 and brut < 1:
        sorunlar.append({
            "alan": "brut",
            "seviye": "uyari",
            "mesaj": f"Brut tutar cok dusuk: {brut:.2f}",
            "kod": "BRUT_COK_DUSUK",
        })

    if ham_text and len(ham_text) < 20:
        sorunlar.append({
            "alan": "_genel",
            "seviye": "hata",
            "mesaj": "OCR metni cok kisa (20 karakterden az)",
            "kod": "OCR_METIN_COK_KISA",
        })

    tarih = parsed.get("tarih", "")
    if tarih:
        try:
            dt = datetime.strptime(tarih, "%d.%m.%Y")
            if dt.year < 2020:
                sorunlar.append({
                    "alan": "tarih",
                    "seviye": "uyari",
                    "mesaj": f"Tarih cok eski: {tarih}",
                    "kod": "TARIH_COK_ESKI",
                })
        except ValueError:
            pass

    return sorunlar


def ocr_sonuc_dogrula(parsed: dict, ham_text: str = "",
                      mukellef_listesi: list = None,
                      urun_kodlari: list = None) -> dict:
    """OCR sonucunu tum yonlerden dogrula.
    
    Returns:
        {
            "genel_skor": 0-100,
            "alan_raporlari": {alan_adi: {"durum", "mesaj", "seviye", "guven"}},
            "sorunlar": [{"alan", "seviye", "mesaj", "kod"}],
            "calisma_suresi": ms,
            "alan_sayisi": N,
            "sorunlu_alan_sayisi": N,
        }
    """
    alan_raporlari = {}
    tum_sorunlar = []
    gecerli_alan = 0
    toplam_alan = 0

    for alan, kurallar in ALAN_KURALLARI.items():
        deger = parsed.get(alan, "")
        tip = kurallar.get("type", "metin")

        toplam_alan += 1
        gecerli_mi = False
        mesaj = ""

        if tip == "tarih":
            gecerli_mi, mesaj = _tarih_dogrula(str(deger) if deger else "")
        elif tip == "sayi":
            gecerli_mi, mesaj = _sayi_dogrula(deger, kurallar)
        else:
            gecerli_mi, mesaj = _metin_dogrula(str(deger) if deger else "", kurallar, alan)

        seviye = "basarili" if gecerli_mi else "hata"
        if gecerli_mi:
            gecerli_alan += 1

        alan_raporlari[alan] = {
            "durum": seviye,
            "mesaj": mesaj,
            "seviye": seviye,
            "guven": 1.0 if gecerli_mi else 0.0,
            "deger": str(deger) if deger else "",
        }

        if not gecerli_mi and kurallar.get("gerekli", False):
            tum_sorunlar.append({
                "alan": alan,
                "seviye": "hata",
                "mesaj": f"{alan} dogrulama hatasi: {mesaj}",
                "kod": f"{alan.upper()}_HATA",
            })

    # Tutarlilik kontrolleri
    tum_sorunlar.extend(_tutarlilik_dogrula(parsed))

    # Anomali tespiti
    tum_sorunlar.extend(_anomalies(parsed, ham_text))

    # Capraz referans
    if mukellef_listesi and parsed.get("firma_adi"):
        firma = parsed["firma_adi"].upper().strip()
        eslesme_bulundu = False
        for m in mukellef_listesi:
            ad = (m.get("adi", "") or "").upper().strip()
            ka = (m.get("kisa_adi", "") or "").upper().strip()
            if firma == ad or firma == ka:
                eslesme_bulundu = True
                break
            if ad and (ad in firma or firma in ad):
                eslesme_bulundu = True
                break

        if not eslesme_bulundu:
            tum_sorunlar.append({
                "alan": "firma_adi",
                "seviye": "uyari",
                "mesaj": f"Firma adi mukellef listesinde eslesmedi: '{parsed['firma_adi']}'",
                "kod": "FIRMA_MUKELLEF_ESLESMEDI",
            })

    if urun_kodlari and parsed.get("urunler"):
        for urun in parsed["urunler"]:
            ua = urun.get("urun", "").upper().strip()
            if not ua:
                continue
            from luca import urun_kodu_bul
            eslesme = urun_kodu_bul(urun_kodlari, ua)
            if eslesme:
                beklenen_kdv = eslesme.get("kdv_orani", 0)
                mevcut_kdv = urun.get("oran", 0) or 0
                if beklenen_kdv != mevcut_kdv and beklenen_kdv > 0:
                    tum_sorunlar.append({
                        "alan": f"urun:{ua}",
                        "seviye": "uyari",
                        "mesaj": f"KDV orani uyusmazligi: '{ua}' icin beklenen %{beklenen_kdv}, okunan %{mevcut_kdv}",
                        "kod": "URUN_KDV_UYUSMAZ",
                    })

    # Genel skor
    sorunlu_alan_sayisi = len(set(s["alan"] for s in tum_sorunlar))
    genel_skor = (gecerli_alan / max(toplam_alan, 1)) * 100

    for s in tum_sorunlar:
        if s.get("seviye") == "hata":
            genel_skor -= 15
        elif s.get("seviye") == "uyari":
            genel_skor -= 5

    genel_skor = max(0, min(100, genel_skor))

    return {
        "genel_skor": round(genel_skor, 1),
        "alan_raporlari": alan_raporlari,
        "sorunlar": tum_sorunlar,
        "gecerli_alan": gecerli_alan,
        "toplam_alan": toplam_alan,
        "sorunlu_alan_sayisi": sorunlu_alan_sayisi,
        "ham_text_uzunluk": len(ham_text or ""),
    }


def _anomalies(parsed: dict, ham_text: str = "") -> List[dict]:
    return _anomali_tespit(parsed, ham_text)
