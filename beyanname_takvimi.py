"""
Beyanname takvimi + otomatik hatirlatici.
KDV, Muhtasar, BA-BS, Gelir Vergisi, Kurumlar Vergisi, Gecici Vergi.
T-7, T-3, T-1, T-0 gunlerinde email bildirimi.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import os


BEYANNAMELER = {
    "KDV1": {
        "ad": "KDV Beyannamesi (Aylık)",
        "donem": "aylik",
        "gun": 28,
        "ay_offset": 1,
        "renk": "#0F766E",
        "aciklama": "Aylık KDV beyannamesi, takip eden ayın 28'i",
    },
    "MUHTASAR": {
        "ad": "Muhtasar ve Prim Hizmet Beyannamesi",
        "donem": "aylik",
        "gun": 26,
        "ay_offset": 1,
        "renk": "#7C3AED",
        "aciklama": "Aylık muhtasar, takip eden ayın 26'sı",
    },
    "BABS": {
        "ad": "BA-BS Formları",
        "donem": "aylik",
        "gun": 5,
        "ay_offset": 2,
        "renk": "#DC2626",
        "aciklama": "BA-BS formları, takip eden 2. ayın 5'i (e-defter zorunluları için)",
    },
    "GECICI_GV": {
        "ad": "Geçici Gelir Vergisi",
        "donem": "3aylik",
        "aylar": [2, 5, 8, 11],
        "gun": 17,
        "ay_offset": 1,
        "renk": "#EA580C",
        "aciklama": "3 ayda bir, takip eden ayın 17'si",
    },
    "GECICI_KV": {
        "ad": "Geçici Kurumlar Vergisi",
        "donem": "3aylik",
        "aylar": [2, 5, 8, 11],
        "gun": 17,
        "ay_offset": 1,
        "renk": "#9333EA",
        "aciklama": "3 ayda bir, takip eden ayın 17'si (kurumlar için)",
    },
    "GV": {
        "ad": "Yıllık Gelir Vergisi Beyannamesi",
        "donem": "yillik",
        "ay": 3,
        "gun": 31,
        "ay_offset": 0,
        "renk": "#0EA5E9",
        "aciklama": "Yıllık, Mart ayı son günü",
    },
    "KV": {
        "ad": "Yıllık Kurumlar Vergisi Beyannamesi",
        "donem": "yillik",
        "ay": 4,
        "gun": 30,
        "ay_offset": 0,
        "renk": "#0284C7",
        "aciklama": "Yıllık, Nisan ayı son günü",
    },
    "KAMU": {
        "ad": "Kamu SM (E-defter berat)",
        "donem": "aylik",
        "gun": 30,
        "ay_offset": 4,
        "renk": "#475569",
        "aciklama": "E-defter berat yükleme, dönem kapandıktan 4 ay sonra",
    },
}


HATIRLATMA_GUNLERI = [7, 3, 1, 0]


def beyanname_tarihi_hesapla(beyanname_adi: str, ref_date: Optional[datetime] = None) -> Optional[datetime]:
    """Belirli bir beyanname icin son gun tarihini hesapla."""
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
            return datetime(yil, ay, gun)
        except ValueError:
            if ay == 2 and gun == 28:
                return datetime(yil, 2, 28)
            from calendar import monthrange
            son_gun = monthrange(yil, ay)[1]
            return datetime(yil, ay, min(gun, son_gun))

    if donem == "3aylik":
        yil = ref_date.year
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
                return datetime(hedef_yil, hedef_ay, min(info["gun"], son_gun))
        return None

    if donem == "yillik":
        yil = ref_date.year + info.get("ay_offset", 0)
        ay = info["ay"]
        gun = info["gun"]
        from calendar import monthrange
        son_gun = monthrange(yil, ay)[1]
        return datetime(yil, ay, min(gun, son_gun))

    return None


def yaklasan_beyannameler(ref_date: Optional[datetime] = None, gun_araligi: int = 30) -> List[Dict]:
    """Yaklasan beyannameleri listele (T-gun_araligi icinde)."""
    if ref_date is None:
        ref_date = datetime.now()

    yaklasan = []
    for kod, info in BEYANNAMELER.items():
        tarih = beyanname_tarihi_hesapla(kod, ref_date)
        if tarih is None:
            continue
        kalan_gun = (tarih - ref_date).days
        if -7 <= kalan_gun <= gun_araligi:
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
                "hatirlatma_gerekli": hatirlatma and kalan_gun >= 0,
            })
    yaklasan.sort(key=lambda x: x["kalan_gun"])
    return yaklasan


def _kalan_gun_text(kalan_gun: int) -> str:
    if kalan_gun == 0:
        return "🔴 BUGÜN!"
    if kalan_gun == 1:
        return "⚠️ YARIN"
    if kalan_gun < 0:
        return f"❌ {abs(kalan_gun)} gün geçti"
    if kalan_gun <= 3:
        return f"⚠️ {kalan_gun} gün kaldı"
    if kalan_gun <= 7:
        return f"⏰ {kalan_gun} gün kaldı"
    return f"📅 {kalan_gun} gün kaldı"


def email_icerik_olustur(yaklasan: List[Dict]) -> Tuple[str, str]:
    """Email konu + icerik olustur."""
    if not yaklasan:
        return "Beyanname Hatırlatıcısı", "Yaklaşan beyanname bulunmuyor."

    konu = f"SMMM Beyanname Hatırlatıcısı: {len(yaklasan)} beyanname"
    satirlar = ["Yaklaşan beyannameler:\n"]
    for b in yaklasan:
        satirlar.append(f"- {b['ad']} ({b['kod']})")
        satirlar.append(f"  Son gün: {b['tarih']} ({b['kalan_text']})")
        satirlar.append(f"  {b['aciklama']}\n")
    icerik = "\n".join(satirlar)
    return konu, icerik
