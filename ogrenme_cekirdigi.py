"""
ogrenme_cekirdigi.py — Istatistiksel OCR ogrenme motoru.

Her duzeltme sayilir, confidence puani hesaplanir.
Yuksek guvenli duzeltmeler otomatik uygulanir.
Geri bildirim dongusu ile surekli iyilesir.
"""
import os
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict, List, Tuple

from config import DATA_DIR
from utils import dosya_oku, dosya_yaz, log, levenshtein

OGRENME_DB = os.path.join(DATA_DIR, "ogrenme_db.json")

# Field categories for smarter correction
ALAN_KATEGORI = {
    "tarih": "tarih",
    "z_no": "no",
    "belge_no": "no",
    "firma_adi": "metin",
    "banka_adi": "metin",
    "brut": "sayi",
    "net_toplam": "sayi",
    "nakit": "sayi",
    "kredi_karti": "sayi",
    "yemek_ceki": "sayi",
    "iadeler": "sayi",
    "toplam_tahsilat": "sayi",
}

# Minimum confidence to auto-apply
AUTO_APPLY_ESIK = 0.75
# Minimum correction count before trusting
MIN_ORNEK_ESIK = 2
# Decay: how many days until a correction loses half its weight
GUVEN_YARILANMA_GUN = 90


def _varsayilan_db() -> dict:
    return {
        "sozluk": {},
        "alan_duzeltme": {},
        "istatistik": {
            "toplam_duzeltme": 0,
            "auto_uygulanan": 0,
            "reddedilen": 0,
        },
        "son_guncelleme": datetime.now().isoformat(),
    }


def ogrenme_db_yukle() -> dict:
    db = dosya_oku(OGRENME_DB, None)
    if db is None:
        db = _varsayilan_db()
    if "istatistik" not in db:
        db["istatistik"] = _varsayilan_db()["istatistik"]
    if "alan_duzeltme" not in db:
        db["alan_duzeltme"] = {}
    if "sozluk" not in db:
        db["sozluk"] = {}
    return db


def ogrenme_db_kaydet(db: dict):
    db["son_guncelleme"] = datetime.now().isoformat()
    dosya_yaz(OGRENME_DB, db)


def _normalize_key(yanlis: str) -> str:
    """Normalize correction key: uppercase, collapse whitespace."""
    if not yanlis:
        return ""
    return re.sub(r'\s+', ' ', yanlis.strip().upper())


def duzeltme_kaydet(yanlis: str, dogru: str, alan_adi: str = "", kaynak: str = "manuel"):
    """Bir duzeltmeyi istatistiksel veritabanina kaydet.
    
    Her ayni duzeltme tekrari guven puani artirir.
    Farkli bir duzeltme gelirse oncekiyle rekabet eder.
    """
    if not yanlis or not dogru or yanlis.strip().upper() == dogru.strip().upper():
        return

    db = ogrenme_db_yukle()
    key = _normalize_key(yanlis)

    if key not in db["sozluk"]:
        db["sozluk"][key] = {
            "dogru": dogru.strip(),
            "sayac": 0,
            "ilk": datetime.now().isoformat(),
            "son": datetime.now().isoformat(),
            "alanlar": {},
            "kaynaklar": {},
        }

    kayit = db["sozluk"][key]
    kayit["sayac"] = kayit.get("sayac", 0) + 1
    kayit["son"] = datetime.now().isoformat()
    kayit["dogru"] = dogru.strip()

    if alan_adi:
        alanlar = kayit.setdefault("alanlar", {})
        alanlar[alan_adi] = alanlar.get(alan_adi, 0) + 1

    kaynaklar = kayit.setdefault("kaynaklar", {})
    kaynaklar[kaynak] = kaynaklar.get(kaynak, 0) + 1

    db["istatistik"]["toplam_duzeltme"] += 1
    ogrenme_db_kaydet(db)


def _guven_hesapla(kayit: dict) -> float:
    """Bir duzeltme kaydı icin guven puani hesapla (0.0 - 1.0).
    
    Faktorler:
    - Kac kere tekrarlandi (sayac)
    - Ne kadar sure once (zamanla azalan guven)
    - Kac farkli kaynaktan geldi
    """
    sayac = kayit.get("sayac", 0)
    if sayac <= 0:
        return 0.0

    # Base confidence from count
    conf = 1.0 - (1.0 / (sayac + 1))

    if sayac < MIN_ORNEK_ESIK:
        conf *= 0.5

    # Time decay
    son_str = kayit.get("son", "")
    if son_str:
        try:
            son_tarih = datetime.fromisoformat(son_str)
            gun_farki = (datetime.now() - son_tarih).days
            if gun_farki > 0:
                decay = 0.5 ** (gun_farki / GUVEN_YARILANMA_GUN)
                conf *= decay
        except (ValueError, TypeError):
            pass

    # Source diversity bonus
    kaynaklar = kayit.get("kaynaklar", {})
    if len(kaynaklar) >= 2:
        conf = min(1.0, conf * 1.2)
    if kaynaklar.get("otomatik", 0) > kaynaklar.get("manuel", 0):
        conf = min(1.0, conf * 0.9)

    return max(0.0, min(1.0, conf))


def ogrenilen_sozluk_istatistik(min_guven: float = 0.0) -> Dict[str, Tuple[str, float]]:
    """Istatistiksel ogrenme db'sinden sozluk olustur.
    Doner: {yanlis: (dogru, guven_puani)}
    """
    db = ogrenme_db_yukle()
    sonuc = {}

    for key, kayit in db["sozluk"].items():
        guven = _guven_hesapla(kayit)
        if guven >= min_guven:
            dogru = kayit.get("dogru", "")
            if dogru:
                sonuc[key] = (dogru, guven)

    return sonuc


def auto_duzeltme_uygula(text: str, alan_adi: str = "") -> Tuple[str, List[dict]]:
    """Ogrenilen duzeltmeleri metne uygula.
    Doner: (duzeltilmis_metin, [{"yanlis", "dogru", "guven", "uygulandi"}])
    """
    db = ogrenme_db_yukle()
    degisiklikler = []

    if not text:
        return text, degisiklikler

    for key, kayit in db["sozluk"].items():
        if not key:
            continue
        dogru = kayit.get("dogru", "")
        if not dogru:
            continue

        guven = _guven_hesapla(kayit)
        alanlar = kayit.get("alanlar", {})

        # If specific field and this correction is for different field, lower confidence
        eslesen_alan = alan_adi and alanlar.get(alan_adi, 0) > 0
        if alan_adi and not eslesen_alan and alanlar:
            guven *= 0.3

        uygula = guven >= AUTO_APPLY_ESIK

        if uygula:
            # Word-boundary replacement
            yeni = re.sub(
                r'(?<!\w)' + re.escape(key) + r'(?!\w)',
                dogru,
                text,
                flags=re.IGNORECASE,
            )
            if yeni != text:
                degisiklikler.append({
                    "yanlis": key,
                    "dogru": dogru,
                    "guven": round(guven, 3),
                    "uygulandi": True,
                })
                text = yeni
                db["istatistik"]["auto_uygulanan"] += 1
        else:
            if re.search(r'(?<!\w)' + re.escape(key) + r'(?!\w)', text, re.IGNORECASE):
                degisiklikler.append({
                    "yanlis": key,
                    "dogru": dogru,
                    "guven": round(guven, 3),
                    "uygulandi": False,
                })

    if degisiklikler:
        ogrenme_db_kaydet(db)

    return text, degisiklikler


def alan_duzeltme_kaydet(alan_adi: str, eski_deger: str, yeni_deger: str, kaynak: str = "manuel"):
    """Alan bazli duzeltme kaydet. Orn: firma_adi 'MGROS' -> 'MİGROS'"""
    if not eski_deger or not yeni_deger or eski_deger.strip().upper() == yeni_deger.strip().upper():
        return

    db = ogrenme_db_yukle()
    alanlar = db.setdefault("alan_duzeltme", {})
    alan_key = f"{alan_adi}::{_normalize_key(eski_deger)}"

    if alan_key not in alanlar:
        alanlar[alan_key] = {
            "alan": alan_adi,
            "yanlis": eski_deger.strip(),
            "dogru": yeni_deger.strip(),
            "sayac": 0,
            "ilk": datetime.now().isoformat(),
            "son": datetime.now().isoformat(),
        }

    kayit = alanlar[alan_key]
    kayit["sayac"] += 1
    kayit["son"] = datetime.now().isoformat()
    kayit["dogru"] = yeni_deger.strip()

    ogrenme_db_kaydet(db)


def alan_duzeltme_uygula(parsed: dict) -> Tuple[dict, List[dict]]:
    """Alan bazli duzeltmeleri parsed sonuca uygula.
    Doner: (guncellenmis_parsed, [{"alan", "eski", "yeni", "guven"}])
    """
    db = ogrenme_db_yukle()
    alanlar_db = db.get("alan_duzeltme", {})
    degisiklikler = []

    for alan_key, kayit in alanlar_db.items():
        alan = kayit.get("alan", "")
        yanlis = kayit.get("yanlis", "")
        dogru = kayit.get("dogru", "")
        sayac = kayit.get("sayac", 0)

        if not alan or not dogru or alan not in parsed:
            continue

        mevcut = parsed.get(alan)
        if not mevcut:
            continue

        mevcut_str = str(mevcut).strip()
        yanlis_norm = _normalize_key(yanlis)

        guven = min(1.0, sayac / (sayac + 1.5))

        if _normalize_key(mevcut_str) == yanlis_norm and guven >= AUTO_APPLY_ESIK:
            degisiklikler.append({
                "alan": alan,
                "eski": mevcut_str,
                "yeni": dogru,
                "guven": round(guven, 3),
            })
            parsed[alan] = dogru

    return parsed, degisiklikler


def istatistik_raporu() -> dict:
    """Ogrenme sisteminin durum raporu."""
    db = ogrenme_db_yukle()
    sozluk = db.get("sozluk", {})

    toplam_kayit = len(sozluk)
    yuksek_guven = 0
    dusuk_guven = 0
    toplam_sayac = sum(k.get("sayac", 0) for k in sozluk.values())

    for kayit in sozluk.values():
        g = _guven_hesapla(kayit)
        if g >= AUTO_APPLY_ESIK:
            yuksek_guven += 1
        else:
            dusuk_guven += 1

    alan_duzeltme = db.get("alan_duzeltme", {})
    alan_sayisi = defaultdict(int)
    for k, v in alan_duzeltme.items():
        alan_sayisi[v.get("alan", "bilinmeyen")] += 1

    return {
        "toplam_kayit": toplam_kayit,
        "yuksek_guven": yuksek_guven,
        "dusuk_guven": dusuk_guven,
        "toplam_duzeltme_sayisi": toplam_sayac,
        "alan_bazli_kayit": dict(alan_sayisi),
        "istatistik": db.get("istatistik", {}),
        "son_guncelleme": db.get("son_guncelleme", ""),
        "auto_esik": AUTO_APPLY_ESIK,
        "min_ornek": MIN_ORNEK_ESIK,
    }


def gecmis_temizle(gun_limiti: int = 365):
    """Eski, dusuk guvenli kayitlari temizle."""
    db = ogrenme_db_yukle()
    sozluk = db.get("sozluk", {})
    silinen = 0
    sinir_tarih = datetime.now() - timedelta(days=gun_limiti)

    silinecek_keys = []
    for key, kayit in sozluk.items():
        son_str = kayit.get("son", "")
        if son_str:
            try:
                son_tarih = datetime.fromisoformat(son_str)
                if son_tarih < sinir_tarih and _guven_hesapla(kayit) < 0.2:
                    silinecek_keys.append(key)
            except (ValueError, TypeError):
                silinecek_keys.append(key)

    for key in silinecek_keys:
        del sozluk[key]
        silinen += 1

    if silinen > 0:
        ogrenme_db_kaydet(db)

    return silinen


def mevcut_sozlukleri_birlestir():
    """Eski dosya tabanli sozlukleri yeni sisteme birlestir (migration).
    Her kayit sadece bir kez import edilir; tekrar import onlenir.
    """
    from ocr import ogrenilen_sozluk, duzeltme_sozlugu
    db = ogrenme_db_yukle()
    import_edildi = db.get("istatistik", {}).get("migration_import", False)
    if import_edildi:
        log.info("Sozluk migration zaten yapilmis, atlaniyor")
        return

    eski_ogrenilen = ogrenilen_sozluk()
    for yanlis, dogru in eski_ogrenilen.items():
        duzeltme_kaydet(yanlis, dogru, kaynak="migration_eski")

    eski_duzeltme = duzeltme_sozlugu()
    for yanlis, dogru in eski_duzeltme.items():
        duzeltme_kaydet(yanlis, dogru, kaynak="migration_sozluk")

    db = ogrenme_db_yukle()
    db["istatistik"]["migration_import"] = True
    ogrenme_db_kaydet(db)
    log.info(f"Sozluk migration tamam: {len(eski_ogrenilen)} ogrenilen + {len(eski_duzeltme)} duzeltme")


def duzeltme_reddet(key: str):
    """Bir duzeltmeyi reddet: sayac dustur, red sayisini artir.
    Uc kez reddedilen duzeltme otomatik silinir.
    """
    if not key:
        return False
    db = ogrenme_db_yukle()
    nkey = _normalize_key(key)
    if nkey not in db["sozluk"]:
        return False
    kayit = db["sozluk"][nkey]
    kayit["sayac"] = max(0, kayit.get("sayac", 1) - 2)
    kayit["son"] = datetime.now().isoformat()
    db["istatistik"]["reddedilen"] = db["istatistik"].get("reddedilen", 0) + 1
    red_sayisi = db["istatistik"]["reddedilen"]
    if kayit["sayac"] <= 0 or red_sayisi > kayit.get("sayac", 0):
        del db["sozluk"][nkey]
    ogrenme_db_kaydet(db)
    return True


def duzeltme_listesi(siralama: str = "guven", limit: int = 50) -> List[dict]:
    """Ogrenilen duzeltmelerin listesi.
    siralama: 'guven' (varsayilan), 'tarih', 'sayac'
    """
    db = ogrenme_db_yukle()
    entries = []
    for key, kayit in db.get("sozluk", {}).items():
        guven = _guven_hesapla(kayit)
        entries.append({
            "key": key,
            "dogru": kayit.get("dogru", ""),
            "guven": round(guven, 3),
            "sayac": kayit.get("sayac", 0),
            "son": kayit.get("son", ""),
            "alanlar": list(kayit.get("alanlar", {}).keys()),
            "kaynaklar": kayit.get("kaynaklar", {}),
        })
    if siralama == "tarih":
        entries.sort(key=lambda x: x.get("son", ""), reverse=True)
    elif siralama == "sayac":
        entries.sort(key=lambda x: x.get("sayac", 0), reverse=True)
    else:
        entries.sort(key=lambda x: x.get("guven", 0), reverse=True)
    return entries[:limit]


def alan_duzeltme_listesi(limit: int = 30) -> List[dict]:
    """Alan bazli duzeltmelerin listesi."""
    db = ogrenme_db_yukle()
    entries = []
    for key, kayit in db.get("alan_duzeltme", {}).items():
        sayac = kayit.get("sayac", 0)
        guven = min(1.0, sayac / (sayac + 1.5))
        entries.append({
            "key": key,
            "alan": kayit.get("alan", ""),
            "yanlis": kayit.get("yanlis", ""),
            "dogru": kayit.get("dogru", ""),
            "guven": round(guven, 3),
            "sayac": sayac,
            "son": kayit.get("son", ""),
        })
    entries.sort(key=lambda x: x.get("guven", 0), reverse=True)
    return entries[:limit]
