"""
Beyanname takvimi + otomatik hatirlatici (Genisletilmis).
KDV, Muhtasar, BA-BS, Gelir Vergisi, Kurumlar Vergisi, Gecici Vergi,
e-Defter, e-Fatura, SGK, BES, GV Stopaj, Damga Vergisi, Muhtasar SGK.

Ozellikler:
- Resmi tatil ve hafta sonu kontrolu (erteleme)
- Mukellef atama sistemi
- Yillik takvim heatmap gorunumu
- T-15, T-7, T-3, T-1, T-0 hatirlatma
- Email/SMS/WhatsApp bildirim
- Beyanname tamamlama takibi (gonderildi/gonderilecek)
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import os


BEYANNAMELER = {
    "KDV1": {
        "ad": "KDV Beyannamesi (Aylik)",
        "donem": "aylik",
        "gun": 28,
        "ay_offset": 1,
        "renk": "#0F766E",
        "aciklama": "Aylik KDV beyannamesi, takip eden ayin 28'i",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "MUHTASAR": {
        "ad": "Muhtasar ve Prim Hizmet Beyannamesi",
        "donem": "aylik",
        "gun": 26,
        "ay_offset": 1,
        "renk": "#7C3AED",
        "aciklama": "Aylik muhtasar, takip eden ayin 26'si",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "BABS": {
        "ad": "BA-BS Formlari",
        "donem": "aylik",
        "gun": 5,
        "ay_offset": 2,
        "renk": "#DC2626",
        "aciklama": "BA-BS formlari, takip eden 2. ayin 5'i (e-defter zorunlulari icin)",
        "kategori": "vergi",
        "zorunlu_ek": ["e-defter"],
    },
    "GECICI_GV": {
        "ad": "Gecici Gelir Vergisi",
        "donem": "3aylik",
        "aylar": [2, 5, 8, 11],
        "gun": 17,
        "ay_offset": 1,
        "renk": "#EA580C",
        "aciklama": "3 ayda bir, takip eden ayin 17'si",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "GECICI_KV": {
        "ad": "Gecici Kurumlar Vergisi",
        "donem": "3aylik",
        "aylar": [2, 5, 8, 11],
        "gun": 17,
        "ay_offset": 1,
        "renk": "#9333EA",
        "aciklama": "3 ayda bir, takip eden ayin 17'si (kurumlar icin)",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "GV": {
        "ad": "Yillik Gelir Vergisi Beyannamesi",
        "donem": "yillik",
        "ay": 3,
        "gun": 31,
        "ay_offset": 0,
        "renk": "#0EA5E9",
        "aciklama": "Yillik, Mart ayi son gunu",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "KV": {
        "ad": "Yillik Kurumlar Vergisi Beyannamesi",
        "donem": "yillik",
        "ay": 4,
        "gun": 30,
        "ay_offset": 0,
        "renk": "#0284C7",
        "aciklama": "Yillik, Nisan ayi son gunu",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "KAMU": {
        "ad": "Kamu SM (E-defter berat)",
        "donem": "aylik",
        "gun": 30,
        "ay_offset": 4,
        "renk": "#475569",
        "aciklama": "E-defter berat yukleme, donem kapandiktan 4 ay sonra",
        "kategori": "e-belge",
        "zorunlu_ek": ["e-defter"],
    },
    "EDEFTER_BERAT": {
        "ad": "E-Defter Berat Dosyasi",
        "donem": "aylik",
        "gun": 30,
        "ay_offset": 3,
        "renk": "#64748B",
        "aciklama": "E-defter berat, donem kapandiktan 3 ay sonra",
        "kategori": "e-belge",
        "zorunlu_ek": ["e-defter"],
    },
    "EFATURA_BERAT": {
        "ad": "E-Fatura Uygulama Berat",
        "donem": "aylik",
        "gun": 30,
        "ay_offset": 1,
        "renk": "#0891B2",
        "aciklama": "E-Fatura berat, takip eden ayin 30'u",
        "kategori": "e-belge",
        "zorunlu_ek": ["e-fatura"],
    },
    "EARŞIV_BERAT": {
        "ad": "E-Arsiv Berat Dosyasi",
        "donem": "aylik",
        "gun": 30,
        "ay_offset": 1,
        "renk": "#0E7490",
        "aciklama": "E-Arsiv berat, takip eden ayin 30'u",
        "kategori": "e-belge",
        "zorunlu_ek": ["e-arsiv"],
    },
    "SGK_AYLIK": {
        "ad": "SGK Aylik Prim ve Hizmet Belgesi",
        "donem": "aylik",
        "gun": 23,
        "ay_offset": 1,
        "renk": "#16A34A",
        "aciklama": "SGK prim bildirgesi, takip eden ayin 23'u",
        "kategori": "sgk",
        "zorunlu_ek": ["sgk-kayitli-calisan"],
    },
    "DAMGA": {
        "ad": "Damga Vergisi Beyannamesi",
        "donem": "yillik",
        "ay": 1,
        "gun": 31,
        "ay_offset": 0,
        "renk": "#DB2777",
        "aciklama": "Yillik Damga Vergisi, Ocak ayi son gunu (kurumlar icin)",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "GV_STOPAJ": {
        "ad": "Gayrimenkul Stopaj Beyannamesi",
        "donem": "yillik",
        "ay": 3,
        "gun": 31,
        "ay_offset": 0,
        "renk": "#BE185D",
        "aciklama": "Gayrimenkul sermaye iradi stopaj, Mart ayi son gunu",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "GECICI_VERGI": {
        "ad": "Gecici Vergi (Genel)",
        "donem": "3aylik",
        "aylar": [3, 6, 9, 12],
        "gun": 17,
        "ay_offset": 1,
        "renk": "#C2410C",
        "aciklama": "Gecici vergi, her ceyrek sonrasi ayin 17'si",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "KONAKLAMA": {
        "ad": "Konaklama Vergisi Beyannamesi",
        "donem": "aylik",
        "gun": 20,
        "ay_offset": 1,
        "renk": "#7E22CE",
        "aciklama": "Konaklama vergisi, takip eden ayin 20'si (turizm sektoru)",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "TURIZM": {
        "ad": "Turizm Payi Beyannamesi",
        "donem": "3aylik",
        "aylar": [4, 7, 10, 1],
        "gun": 20,
        "ay_offset": 1,
        "renk": "#9333EA",
        "aciklama": "Turizm payi, ceyreklik donem (otel/restoran isletmeleri)",
        "kategori": "vergi",
        "zorunlu_ek": [],
    },
    "POSET": {
        "ad": "Poşet Beyannamesi",
        "donem": "yillik",
        "ay": 1,
        "gun": 31,
        "ay_offset": 0,
        "renk": "#059669",
        "aciklama": "Plastik poşet beyannamesi, Ocak ayi son gunu",
        "kategori": "cevre",
        "zorunlu_ek": [],
    },
}


HATIRLATMA_GUNLERI = [15, 7, 3, 1, 0]


# 2024-2030 yillari icin onemli resmi tatiller (Türkiye)
# Veriler basitlestirilmis - sadece sabit tatiller, her yil guncellenmeli
RESMI_TATILLER = {
    2024: [
        (1, 1),   # Yilbasi
        (4, 23),  # Ulusal Egemenlik ve Cocuk Bayrami
        (5, 1),   # Emek ve Dayanisma Gunu
        (5, 19),  # Atatürk'ü Anma Genclik ve Spor Bayrami
        (7, 15),  # Demokrasi ve Milli Birlik Gunu
        (8, 30),  # Zafer Bayrami
        (10, 29),  # Cumhuriyet Bayrami
    ],
    2025: [
        (1, 1),
        (4, 23),
        (5, 1),
        (5, 19),
        (7, 15),
        (8, 30),
        (10, 29),
        (3, 30),  # Ramazan Bayrami (1. gun)
        (3, 31),
        (4, 1),
        (6, 6),   # Kurban Bayrami (1. gun)
        (6, 7),
        (6, 8),
        (6, 9),
    ],
    2026: [
        (1, 1),
        (4, 23),
        (5, 1),
        (5, 19),
        (7, 15),
        (8, 30),
        (10, 29),
        (3, 20),  # Ramazan Bayrami (1. gun)
        (3, 21),
        (3, 22),
        (5, 27),  # Kurban Bayrami (1. gun)
        (5, 28),
        (5, 29),
        (5, 30),
    ],
    2027: [
        (1, 1),
        (4, 23),
        (5, 1),
        (5, 19),
        (7, 15),
        (8, 30),
        (10, 29),
        (3, 9),   # Ramazan Bayrami
        (3, 10),
        (3, 11),
        (5, 16),  # Kurban Bayrami
        (5, 17),
        (5, 18),
        (5, 19),
    ],
}


def resmi_tatil_mi(tarih: datetime) -> bool:
    """Belirtilen tarih resmi tatil mi?"""
    yil = tarih.year
    if yil in RESMI_TATILLER:
        return (tarih.month, tarih.day) in RESMI_TATILLER[yil]
    return False


def is_tatil_veya_h_sonu(tarih: datetime) -> bool:
    """Tatil mi, hafta sonu mu kontrol et."""
    if tarih.weekday() >= 5:  # Cumartesi=5, Pazar=6
        return True
    return resmi_tatil_mi(tarih)


def son_is_gununu_bul(tarih: datetime) -> datetime:
    """Son gun hafta sonu veya tatilse, onceki is gununu bul.

    Türkiye uygulamasinda: Beyanname son gunu hafta sonu/tatile denk gelirse,
    sonraki ilk is gunu degil, bir onceki is gunu kabul edilir.
    (Bazi durumlar tersi olabilir, kontrol gerekir)
    """
    from calendar import monthrange
    donem_ay = tarih.month
    donem_yil = tarih.year
    son_gun = monthrange(donem_yil, donem_ay)[1]

    # Beyanname son gunu olarak ayin gununu al
    hedef = datetime(donem_yil, donem_ay, min(tarih.day, son_gun))

    # Eger hedef is gunu degilse, bir onceki is gununu bul
    while is_tatil_veya_h_sonu(hedef):
        hedef -= timedelta(days=1)
        # Guvenlik: minimum 1'e dusmesin
        if hedef.day < 1:
            hedef = datetime(donem_yil, donem_ay, 1)
            while is_tatil_veya_h_sonu(hedef):
                hedef += timedelta(days=1)
            break
    return hedef


def beyanname_tarihi_hesapla(beyanname_adi: str, ref_date: Optional[datetime] = None,
                              tatil_erteleme: bool = True) -> Optional[datetime]:
    """Belirli bir beyanname icin son gun tarihini hesapla.

    Args:
        beyanname_adi: Beyanname kodu
        ref_date: Referans tarihi (None ise simdi)
        tatil_erteleme: True ise hafta sonu/tatil kontrolu yap
    """
    if beyanname_adi not in BEYANNAMELER:
        return None
    info = BEYANNAMELER[beyanname_adi]
    if ref_date is None:
        ref_date = datetime.now()

    donem = info["donem"]
    if donem == "aylik":
        yil = ref_date.year
        ay = ref_date.month + info.get("ay_offset", 1)
        if ay > 12:
            ay -= 12
            yil += 1
        gun = info["gun"]
        try:
            hesaplanan = datetime(yil, ay, gun)
        except ValueError:
            if ay == 2 and gun == 28:
                hesaplanan = datetime(yil, 2, 28)
            else:
                from calendar import monthrange
                son_gun = monthrange(yil, ay)[1]
                hesaplanan = datetime(yil, ay, min(gun, son_gun))
    elif donem == "3aylik":
        yil = ref_date.year
        hesaplanan = None
        for offset in range(0, 4):
            try_ay = ref_date.month + offset
            try_yil = yil
            if try_ay > 12:
                try_ay -= 12
                try_yil += 1
            if try_ay in info["aylar"]:
                hedef_ay = try_ay + info.get("ay_offset", 1)
                hedef_yil = try_yil
                if hedef_ay > 12:
                    hedef_ay -= 12
                    hedef_yil += 1
                from calendar import monthrange
                son_gun = monthrange(hedef_yil, hedef_ay)[1]
                hesaplanan = datetime(hedef_yil, hedef_ay, min(info["gun"], son_gun))
                break
        if hesaplanan is None:
            return None
    elif donem == "yillik":
        yil = ref_date.year + info.get("ay_offset", 0)
        ay = info["ay"]
        gun = info["gun"]
        from calendar import monthrange
        son_gun = monthrange(yil, ay)[1]
        hesaplanan = datetime(yil, ay, min(gun, son_gun))
    else:
        return None

    if tatil_erteleme:
        hesaplanan = son_is_gununu_bul(hesaplanan)

    return hesaplanan


def _kalan_gun_text(kalan_gun: int) -> str:
    if kalan_gun == 0:
        return "BUGUN SON GUN"
    if kalan_gun == 1:
        return "YARIN SON GUN"
    if kalan_gun < 0:
        return f"! {abs(kalan_gun)} gun gecti"
    if kalan_gun <= 3:
        return f"! {kalan_gun} gun kaldi"
    if kalan_gun <= 7:
        return f"-> {kalan_gun} gun kaldi"
    if kalan_gun <= 15:
        return f"<> {kalan_gun} gun kaldi"
    return f"-- {kalan_gun} gun kaldi"


def yaklasan_beyannameler(ref_date: Optional[datetime] = None,
                          gun_araligi: int = 30,
                          kategori: Optional[str] = None) -> List[Dict]:
    """Yaklasan beyannameleri listele.

    Args:
        ref_date: Referans tarihi
        gun_araligi: T+days icindekileri getir
        kategori: filtre (vergi, e-belge, sgk, ...)
    """
    if ref_date is None:
        ref_date = datetime.now()

    yaklasan = []
    for kod, info in BEYANNAMELER.items():
        if kategori and info.get("kategori") != kategori:
            continue
        tarih = beyanname_tarihi_hesapla(kod, ref_date, tatil_erteleme=True)
        if tarih is None:
            continue
        kalan_gun = (tarih - ref_date).days
        if -30 <= kalan_gun <= gun_araligi:
            hatirlatma = kalan_gun in HATIRLATMA_GUNLERI
            yaklasan.append({
                "kod": kod,
                "ad": info["ad"],
                "tarih": tarih.strftime("%d.%m.%Y"),
                "tarih_iso": tarih.strftime("%Y-%m-%d"),
                "kalan_gun": kalan_gun,
                "kalan_text": _kalan_gun_text(kalan_gun),
                "aciklama": info["aciklama"],
                "renk": info["renk"],
                "kategori": info.get("kategori", "diger"),
                "donem": info["donem"],
                "hatirlatma_gerekli": hatirlatma and kalan_gun >= 0,
            })
    yaklasan.sort(key=lambda x: x["kalan_gun"])
    return yaklasan


def yillik_takvim(yil: int, mukellef_atamalari: Optional[Dict] = None) -> List[Dict]:
    """Bir yil icin tum beyannameleri listele."""
    baslangic = datetime(yil, 1, 1)
    bitis = datetime(yil, 12, 31)
    tum_veri = []

    current = baslangic
    while current <= bitis:
        for kod, info in BEYANNAMELER.items():
            tarih = beyanname_tarihi_hesapla(kod, current, tatil_erteleme=True)
            if tarih and tarih.year == current.year:
                kayit = {
                    "kod": kod,
                    "ad": info["ad"],
                    "tarih": tarih.strftime("%d.%m.%Y"),
                    "ay": tarih.month,
                    "gun": tarih.day,
                    "kategori": info.get("kategori", "diger"),
                    "renk": info["renk"],
                }
                if mukellef_atamalari and kod in mukellef_atamalari:
                    kayit["mukellef_sayisi"] = len(mukellef_atamalari[kod])
                tum_veri.append(kayit)
        current += timedelta(days=1)

    # Tekrarlari kaldir
    gorulenler = set()
    tekil_veri = []
    for kayit in tum_veri:
        key = (kayit["kod"], kayit["ay"])
        if key not in gorulenler:
            gorulenler.add(key)
            tekil_veri.append(kayit)
    return tekil_veri


def aylik_heatmap(yil: int, ay: int) -> Dict:
    """Belirli bir ay icin beyanname yogunluk haritasi."""
    baslangic = datetime(yil, ay, 1)
    heatmap = {gun: [] for gun in range(1, 32)}

    for kod, info in BEYANNAMELER.items():
        tarih = beyanname_tarihi_hesapla(kod, baslangic, tatil_erteleme=True)
        if tarih and tarih.year == yil and tarih.month == ay:
            try:
                heatmap[tarih.day].append({
                    "kod": kod,
                    "ad": info["ad"],
                    "renk": info["renk"],
                })
            except KeyError:
                pass
    return heatmap


def email_icerik_olustur(yaklasan: List[Dict], mukellef_listesi: Optional[List[str]] = None) -> Tuple[str, str]:
    """Email konu + icerik olustur."""
    if not yaklasan:
        return "Beyanname Hatirlatici", "Yaklasan beyanname bulunmuyor."

    konu = f"SMMM Beyanname Hatirlatici: {len(yaklasan)} beyanname"
    satirlar = ["Yaklasan beyannameler:\n"]
    for b in yaklasan:
        satir = f"- {b['ad']} ({b['kod']})"
        if b['kalan_gun'] == 0:
            satir = "[BUGUN] " + satir
        elif b['kalan_gun'] == 1:
            satir = "[YARIN] " + satir
        satirlar.append(satir)
        satirlar.append(f"  Son gun: {b['tarih']} ({b['kalan_text']})")
        satirlar.append(f"  {b['aciklama']}\n")

    if mukellef_listesi:
        satirlar.append(f"\nIlgili mukellef sayisi: {len(mukellef_listesi)}")

    icerik = "\n".join(satirlar)
    return konu, icerik


# ==== Mukellef atama sistemi ====
MUKELLEF_BEYANNAME_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "beyanname_atamalari.json"
)


def mukellef_atamalari_yukle() -> Dict:
    """Mukellef-beyanname atamalarini yukle."""
    if not os.path.exists(MUKELLEF_BEYANNAME_FILE):
        return {}
    try:
        with open(MUKELLEF_BEYANNAME_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def mukellef_atamasi_kaydet(beyanname_kod: str, mukellef_listesi: List[str]) -> bool:
    """Mukellef listesini beyannameye ata."""
    atamalar = mukellef_atamalari_yukle()
    atamalar[beyanname_kod] = mukellef_listesi
    try:
        os.makedirs(os.path.dirname(MUKELLEF_BEYANNAME_FILE), exist_ok=True)
        with open(MUKELLEF_BEYANNAME_FILE, "w", encoding="utf-8") as f:
            json.dump(atamalar, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def mukellef_atamasi_sil(beyanname_kod: str) -> bool:
    """Mukellef atamasini sil."""
    atamalar = mukellef_atamalari_yukle()
    if beyanname_kod in atamalar:
        del atamalar[beyanname_kod]
        try:
            with open(MUKELLEF_BEYANNAME_FILE, "w", encoding="utf-8") as f:
                json.dump(atamalar, f, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False
    return False


def tamamlanma_durumu_yukle() -> Dict:
    """Beyanname tamamlanma (gonderildi/beklemede) durumunu yukle."""
    durum_dosyasi = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "beyanname_tamamlanma.json"
    )
    if not os.path.exists(durum_dosyasi):
        return {}
    try:
        with open(durum_dosyasi, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def tamamlanma_kaydet(anahtar: str, durum: str, notu: str = "") -> bool:
    """Beyanname tamamlanma durumunu kaydet.

    durum: 'tamamlandi', 'beklemede', 'gecikti'
    """
    tum_durum = tamamlanma_durumu_yukle()
    tum_durum[anahtar] = {
        "durum": durum,
        "notu": notu,
        "tarih": datetime.now().isoformat(),
    }
    dosya = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "beyanname_tamamlanma.json"
    )
    try:
        os.makedirs(os.path.dirname(dosya), exist_ok=True)
        with open(dosya, "w", encoding="utf-8") as f:
            json.dump(tum_durum, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def tamamlanma_oku(anahtar: str) -> Optional[Dict]:
    """Belirli bir beyannamenin tamamlanma durumunu getir."""
    tum_durum = tamamlanma_durumu_yukle()
    return tum_durum.get(anahtar)


def donem_anahtari(beyanname_kod: str, tarih: datetime) -> str:
    """Beyanname donemi icin unique anahtar olustur."""
    return f"{beyanname_kod}_{tarih.strftime('%Y%m')}"


def istatistik(ref_date: Optional[datetime] = None) -> Dict:
    """Beyanname istatistikleri."""
    if ref_date is None:
        ref_date = datetime.now()

    yaklasan_30 = yaklasan_beyannameler(ref_date, 30)
    yaklasan_60 = yaklasan_beyannameler(ref_date, 60)
    tum = yaklasan_beyannameler(ref_date, 365)

    tamamlanma = tamamlanma_durumu_yukle()
    tamamlanan = sum(1 for d in tamamlanma.values() if d.get("durum") == "tamamlandi")

    return {
        "yaklasan_30_gun": len(yaklasan_30),
        "yaklasan_60_gun": len(yaklasan_60),
        "yaklasan_365_gun": len(tum),
        "kritik_bugun": len([b for b in yaklasan_30 if b["kalan_gun"] <= 0]),
        "kritik_3_gun": len([b for b in yaklasan_30 if b["kalan_gun"] <= 3]),
        "kategoriler": {
            "vergi": len([b for b in yaklasan_30 if b["kategori"] == "vergi"]),
            "e-belge": len([b for b in yaklasan_30 if b["kategori"] == "e-belge"]),
            "sgk": len([b for b in yaklasan_30 if b["kategori"] == "sgk"]),
        },
        "tamamlanan_toplam": tamamlanan,
        "toplam_beyanname_turu": len(BEYANNAMELER),
    }


# ==== Bildirim Log Sistemi ====
BILDIRIM_LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "bildirim_log.json"
)


def bildirim_log_kaydet(tur: str, beyanname_kod: str, mesaj: str, basarili: bool = True):
    """Bildirim gonderimini logla."""
    loglar = _bildirim_log_yukle()
    loglar.append({
        "tur": tur,
        "beyanname_kod": beyanname_kod,
        "mesaj": mesaj,
        "basarili": basarili,
        "tarih": datetime.now().isoformat(),
    })
    try:
        os.makedirs(os.path.dirname(BILDIRIM_LOG_FILE), exist_ok=True)
        with open(BILDIRIM_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(loglar[-500:], f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _bildirim_log_yukle() -> List[Dict]:
    if not os.path.exists(BILDIRIM_LOG_FILE):
        return []
    try:
        with open(BILDIRIM_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def bildirim_log_listele(limit: int = 50, tur: Optional[str] = None) -> List[Dict]:
    """Bildirim loglarini listele."""
    loglar = _bildirim_log_yukle()
    if tur:
        loglar = [l for l in loglar if l.get("tur") == tur]
    return loglar[-limit:]


def bildirim_log_temizle():
    """Tum bildirim loglarini temizle."""
    try:
        os.makedirs(os.path.dirname(BILDIRIM_LOG_FILE), exist_ok=True)
        with open(BILDIRIM_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return True
    except OSError:
        return False


def otomatik_email_kontrol() -> List[Dict]:
    """T-15/T-7/T-3/T-1/T-0 kontrolu yap.
    
    Hangi beyannameler icin bildirim gonderilmesi gerektigini dondur.
    Her beyanname icin son 24 saatte bildirim gonderilmemis olmali.
    """
    bugun = datetime.now()
    son_24 = bugun - timedelta(hours=24)
    loglar = _bildirim_log_yukle()
    
    gonderilecek = []
    for b in yaklasan_beyannameler(bugun, 30):
        kalan = b["kalan_gun"]
        if kalan not in HATIRLATMA_GUNLERI or kalan < 0:
            continue
        
        # Son 24 saatte bildirim gonderilmis mi kontrol et
        gonderilmemis = True
        for log in loglar:
            if log.get("beyanname_kod") == b["kod"]:
                try:
                    log_tarih = datetime.fromisoformat(log["tarih"])
                    if log_tarih > son_24:
                        gonderilmemis = False
                        break
                except (ValueError, KeyError):
                    pass
        
        if gonderilmemis:
            gonderilecek.append(b)
    
    return gonderilecek


# ==== Mukellef bazli liste ====
def mukellef_bazli_liste(mukellef_adi: str, ref_date: Optional[datetime] = None,
                          gun_araligi: int = 90) -> List[Dict]:
    """Belirli bir mukellefe atanmis beyannameleri listele."""
    if ref_date is None:
        ref_date = datetime.now()
    
    atamalar = mukellef_atamalari_yukle()
    tum_yaklasan = yaklasan_beyannameler(ref_date, gun_araligi)
    sonuc = []
    
    for b in tum_yaklasan:
        if b["kod"] in atamalar and mukellef_adi in atamalar[b["kod"]]:
            sonuc.append(b)
    
    return sonuc


# ==== Export fonksiyonlari ====
def takvim_export_csv(yil: int) -> str:
    """Yillik takvimi CSV olarak export et."""
    takvim = yillik_takvim(yil)
    if not takvim:
        return ""
    
    baslik = "Kod;Ad;Tarih;Kategori\n"
    satirlar = [
        f"{t['kod']};{t['ad']};{t['tarih']};{t['kategori']}"
        for t in takvim
    ]
    return baslik + "\n".join(satirlar)


def takvim_export_json(yil: int) -> str:
    """Yillik takvimi JSON olarak export et."""
    takvim = yillik_takvim(yil)
    return json.dumps(takvim, ensure_ascii=False, indent=2)


# ==== Dashboard grafik verisi ====
def aylik_tamamlanma_istatistik(yil: int) -> Dict[int, Dict]:
    """Yillik aylik bazda tamamlanma istatistikleri."""
    tum_durum = tamamlanma_durumu_yukle()
    aylar = {}
    
    for ay in range(1, 13):
        aylar[ay] = {
            "toplam": 0,
            "tamamlandi": 0,
            "beklemede": 0,
            "gecikti": 0,
        }
    
    for anahtar, durum in tum_durum.items():
        try:
            _, yilay = anahtar.split("_")
            kayit_yil = int(yilay[:4])
            kayit_ay = int(yilay[4:6])
            if kayit_yil == yil:
                aylar[kayit_ay]["toplam"] += 1
                durum_adi = durum.get("durum", "beklemede")
                if durum_adi in aylar[kayit_ay]:
                    aylar[kayit_ay][durum_adi] += 1
        except (ValueError, IndexError):
            pass
    
    return aylar


if __name__ == "__main__":
    print("Beyanname Takvimi Test")
    print("=" * 60)
    print(f"Toplam beyanname turu: {len(BEYANNAMELER)}")
    print()
    print("Yaklasan 30 gun:")
    for b in yaklasan_beyannameler():
        durum = "[BUGUN]" if b['kalan_gun'] == 0 else ""
        print(f"  {durum} {b['ad']:50} {b['tarih']} ({b['kalan_text']})")
    print()
    print("Istatistik:")
    for k, v in istatistik().items():
        print(f"  {k:25}: {v}")
