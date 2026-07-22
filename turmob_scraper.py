"""
TURMOB Mali Takvim Scraper.
https://www.turmob.org.tr/MaliTakvim/{yil}/{ay}/1 adresinden
verileri ceker, parse eder, onceden cekilenle karsilastirir.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import os
import re
import html

import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CACHE_FILE = os.path.join(DATA_DIR, "turmob_takvim_cache.json")
LOG_FILE = os.path.join(DATA_DIR, "turmob_scraper_log.json")
BASE_URL = "https://www.turmob.org.tr/MaliTakvim/{yil}/{ay}/1"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    return DATA_DIR


def _cache_yukle() -> Dict:
    """Onceden cekilmis TURMOB takvim verisini yukle."""
    if not os.path.exists(CACHE_FILE):
        return {"son_guncelleme": None, "veriler": []}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"son_guncelleme": None, "veriler": []}


def _cache_kaydet(veriler: List[Dict]):
    """Cekilen veriyi cache'e kaydet."""
    _data_dir()
    cache = {
        "son_guncelleme": datetime.now().isoformat(),
        "veriler": veriler,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _log_kaydet(seviye: str, mesaj: str):
    """Scraper loguna kaydet."""
    _data_dir()
    loglar = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                loglar = json.load(f)
        except (json.JSONDecodeError, OSError):
            loglar = []
    loglar.append({
        "tarih": datetime.now().isoformat(),
        "seviye": seviye,
        "mesaj": mesaj,
    })
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(loglar[-200:], f, ensure_ascii=False, indent=2)


def _decode_html(text: str) -> str:
    """HTML entity'leri coz (&#246; -> o, &uuml; -> u vb.)."""
    replacements = {
        "&#246;": "ö", "&#214;": "Ö",
        "&#252;": "ü", "&#220;": "Ü",
        "&#231;": "ç", "&#199;": "Ç",
        "&#287;": "ğ", "&#286;": "Ğ",
        "&#305;": "ı", "&#304;": "İ",
        "&#351;": "ş", "&#350;": "Ş",
        "&nbsp;": " ",
    }
    for kod, char in replacements.items():
        text = text.replace(kod, char)
    text = html.unescape(text)
    return text


def _sayfayi_cek(yil: int, ay: int, sayfa: int = 1) -> Optional[str]:
    """TURMOB Mali Takvim sayfasini HTTP GET ile cek."""
    url = f"https://www.turmob.org.tr/MaliTakvim/{yil}/{ay}/{sayfa}"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r.text
    except requests.RequestException as e:
        _log_kaydet("HATA", f"Fetch basarisiz: {url} - {e}")
        return None


def _parse_list_items(html_text: str) -> List[Dict]:
    """HTML icinden <ul class='list-view-link'> listesini parse et.

    Her bir <li>:
      <p class="text-dark mb-2">Beyanname Adi</p>
      <small class="text-dark">01.01.2026 - 31.01.2026</small>
    """
    items = []

    # <ul class="list-view-link"> ... </ul> icindeki tum <li>leri bul
    ul_match = re.search(
        r'<ul\s+class="list-view-link">(.*?)</ul>',
        html_text, re.DOTALL
    )
    if not ul_match:
        return items

    ul_content = ul_match.group(1)

    # Her <li> icindeki <p> ve <small>'i ayikla
    li_pattern = re.compile(
        r'<li>(.*?)</li>', re.DOTALL
    )
    p_pattern = re.compile(
        r'<p[^>]*class="text-dark[^"]*"[^>]*>(.*?)</p>', re.DOTALL
    )
    small_pattern = re.compile(
        r'<small[^>]*class="text-dark[^"]*"[^>]*>(.*?)</small>', re.DOTALL
    )

    for li_match in li_pattern.finditer(ul_content):
        li_html = li_match.group(1)

        p_m = p_pattern.search(li_html)
        baslik = p_m.group(1).strip() if p_m else ""

        small_m = small_pattern.search(li_html)
        tarih_str = small_m.group(1).strip() if small_m else ""

        if not baslik:
            continue

        baslik = _decode_html(baslik)
        tarih_str = _decode_html(tarih_str)

        # Tarih araligini ayristir: "01.12.2025 - 10.03.2026"
        tarih_araligi = tarih_str.replace("(", "").replace(")", "").strip()
        bas_tarih = ""
        bitis_tarih = ""

        tarih_match = re.match(
            r'(\d{2}\.\d{2}\.\d{4})\s*[-–]\s*(\d{2}\.\d{2}\.\d{4})',
            tarih_araligi
        )
        if tarih_match:
            bas_tarih = tarih_match.group(1)
            bitis_tarih = tarih_match.group(2)

        items.append({
            "baslik": baslik,
            "bas_tarih": bas_tarih,
            "bitis_tarih": bitis_tarih,
            "tarih_str": tarih_araligi,
        })

    return items


def tum_sayfaları_cek(yil: int, ay: int) -> List[Dict]:
    """Belirli bir ayin tum sayfalarini cek ve birlestir."""
    tum_ogeler = []
    sayfa_no = 1

    while True:
        html_text = _sayfayi_cek(yil, ay, sayfa_no)
        if not html_text:
            break

        sayfa_ogeleri = _parse_list_items(html_text)
        if not sayfa_ogeleri:
            break

        tum_ogeler.extend(sayfa_ogeleri)

        # Sonraki sayfa var mi kontrol et
        # Sayfalamada "active" class'li <li> varsa, sonraki sayfa linki var mi bak
        next_link = re.search(
            r'<a\s+class="page-link"[^>]*href="[^"]*/'
            + str(yil) + r'/' + str(ay) + r'/' + str(sayfa_no + 1)
            + r'"[^>]*>',
            html_text
        )
        if not next_link:
            break

        sayfa_no += 1

    return tum_ogeler


def tum_yili_cek(yil: int) -> List[Dict]:
    """Bir yil icin tum aylari tara."""
    tum_veri = []
    for ay in range(1, 13):
        ay_ogeleri = tum_sayfaları_cek(yil, ay)
        for o in ay_ogeleri:
            o["yil"] = yil
            o["ay"] = ay
        tum_veri.extend(ay_ogeleri)
    return tum_veri


def guncelle(yil: Optional[int] = None) -> Dict:
    """TURMOB verisini cek, cache ile karsilastir, sonucu dondur.

    Returns:
        {
            "yeni_ogeler": [...],
            "kaldirilan_ogeler": [...],
            "toplam_eski": int,
            "toplam_yeni": int,
            "son_guncelleme": str,
        }
    """
    if yil is None:
        yil = datetime.now().year

    onceki_cache = _cache_yukle()
    onceki_veri = onceki_cache.get("veriler", [])

    yeni_veri = tum_yili_cek(yil)

    # Karsilastirma: baslik bazinda
    onceki_set = set()
    for o in onceki_veri:
        if o.get("yil") == yil:
            onceki_set.add((o["baslik"], o.get("bas_tarih", ""), o.get("bitis_tarih", "")))

    yeni_set = set()
    for o in yeni_veri:
        yeni_set.add((o["baslik"], o.get("bas_tarih", ""), o.get("bitis_tarih", "")))

    yeni_ogeler = [o for o in yeni_veri if (o["baslik"], o.get("bas_tarih", ""), o.get("bitis_tarih", "")) not in onceki_set]
    kaldirilan = [o for o in onceki_veri if o.get("yil") == yil and (o["baslik"], o.get("bas_tarih", ""), o.get("bitis_tarih", "")) not in yeni_set]

    _cache_kaydet(yeni_veri)

    sonuc = {
        "yeni_ogeler": yeni_ogeler,
        "kaldirilan_ogeler": kaldirilan,
        "toplam_eski": len(onceki_veri),
        "toplam_yeni": len(yeni_veri),
        "son_guncelleme": datetime.now().isoformat(),
    }

    if yeni_ogeler:
        _log_kaydet("BILGI", f"{len(yeni_ogeler)} yeni oge bulundu (TURMOB {yil})")
    if kaldirilan:
        _log_kaydet("UYARI", f"{len(kaldirilan)} oge kaldirilmis (TURMOB {yil})")

    return sonuc


def son_durum() -> Dict:
    """Cache'teki son durumu getir."""
    return _cache_yukle()


def log_listele(limit: int = 20) -> List[Dict]:
    """Scraper loglarini listele."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            loglar = json.load(f)
        return loglar[-limit:]
    except (json.JSONDecodeError, OSError):
        return []


def ogeleri_beyanname_ile_karsilastir(turmob_ogeleri: List[Dict]) -> Dict:
    """TURMOB ogelerini bizim BEYANNAMELER ile karsilastir.
    
    Her ogeyi kategorize et: eslesen, eslesmeyen, kategorize_edilemeyen.
    """
    from beyanname_takvimi import BEYANNAMELER

    # Keyword mapping: TURMOB baslik -> bizim beyanname kodu
    anahtar_kelimeler = {
        "e-defter berat": "EDEFTER_BERAT",
        "elektronik defter berat": "EDEFTER_BERAT",
        "e-fatura berat": "EFATURA_BERAT",
        "e-arşiv berat": "EARŞIV_BERAT",
        "e-arsiv berat": "EARŞIV_BERAT",
        "kdv": "KDV1",
        "muhtasar": "MUHTASAR",
        "ba-bs": "BABS",
        "geçici vergi": "GECICI_VERGI",
        "gelir vergisi": "GV",
        "kurumlar vergisi": "KV",
        "sgk": "SGK_AYLIK",
        "damga vergisi": "DAMGA",
        "konaklama vergisi": "KONAKLAMA",
        "turizm": "TURIZM",
        "poşet": "POSET",
    }

    eslesen = []
    eslesmeyen = []

    for o in turmob_ogeleri:
        baslik_lower = o["baslik"].lower()
        eslesti_kod = None

        # 1. Anahtar kelime ile eslestir
        for keyword, kod in anahtar_kelimeler.items():
            if keyword in baslik_lower:
                eslesti_kod = kod
                break

        # 2. BEYANNAMELER adi ile eslestir
        if not eslesti_kod:
            for kod, info in BEYANNAMELER.items():
                if info["ad"].lower() in baslik_lower:
                    eslesti_kod = kod
                    break

        o["eslesti_kod"] = eslesti_kod
        if eslesti_kod:
            o["eslesti_ad"] = BEYANNAMELER[eslesti_kod]["ad"]
            eslesen.append(o)
        else:
            eslesmeyen.append(o)

    return {
        "eslesen": eslesen,
        "eslesmeyen": eslesmeyen,
        "toplam": len(turmob_ogeleri),
        "eslesen_sayisi": len(eslesen),
        "eslesmeyen_sayisi": len(eslesmeyen),
    }


def gunluk_kontrol_ve_bildirim() -> Dict:
    """Her gun cagrilacak: TURMOB'u tara, fark varsa bildir.
    
    Returns:
        {
            "guncellendi": bool,
            "yeni_oge_var": bool,
            "mesaj": str,
            "sonuc": Dict,
        }
    """
    yil = datetime.now().year
    sonuc = guncelle(yil)

    mesaj = f"TÜRMOB {yil} takvimi: {sonuc['toplam_yeni']} öğe"
    if sonuc["yeni_ogeler"]:
        mesaj += f", {len(sonuc['yeni_ogeler'])} yeni eklendi"
    if sonuc["kaldirilan_ogeler"]:
        mesaj += f", {len(sonuc['kaldirilan_ogeler'])} kaldırıldı"

    # Beyanname karsilastirmasi
    karsilastirma = ogeleri_beyanname_ile_karsilastir(sonuc.get("yeni_ogeler", []))
    if karsilastirma["eslesmeyen_sayisi"] > 0:
        mesaj += f", {karsilastirma['eslesmeyen_sayisi']} yeni öğe beyanname listemizle eşleşmedi"

    return {
        "guncellendi": True,
        "yeni_oge_var": len(sonuc["yeni_ogeler"]) > 0,
        "mesaj": mesaj,
        "sonuc": sonuc,
        "karsilastirma": karsilastirma,
    }


def kisa_ozet() -> Dict:
    """Hizli ozet bilgisi - UI icin."""
    cache = son_durum()
    veri = cache.get("veriler", [])
    yil = datetime.now().year

    bugun_ay = datetime.now().month
    bu_ay_ogeler = [o for o in veri if o.get("yil") == yil and o.get("ay") == bugun_ay]

    # Bu ay icinde aktif (bitis tarihi gecmemis) ogeler
    aktif = []
    for o in bu_ay_ogeler:
        try:
            bitis = datetime.strptime(o["bitis_tarih"], "%d.%m.%Y")
            if bitis >= datetime.now():
                aktif.append(o)
        except (ValueError, KeyError):
            pass

    # Karsilastirma
    karsilastirma = ogeleri_beyanname_ile_karsilastir(veri)

    return {
        "toplam_oge": len(veri),
        "bu_ay_oge": len(bu_ay_ogeler),
        "bu_ay_aktif": len(aktif),
        "son_guncelleme": cache.get("son_guncelleme"),
        "eslesmeyen_sayisi": karsilastirma["eslesmeyen_sayisi"],
    }


if __name__ == "__main__":
    import sys
    print("TURMOB Mali Takvim Scraper")
    print("=" * 60)

    yil = datetime.now().year
    if len(sys.argv) > 1:
        try:
            yil = int(sys.argv[1])
        except ValueError:
            pass

    print(f"{yil} yili taranıyor...")
    sonuc = guncelle(yil)
    print(f"Eski: {sonuc['toplam_eski']} oge")
    print(f"Yeni: {sonuc['toplam_yeni']} oge")
    print(f"Yeni eklenen: {len(sonuc['yeni_ogeler'])}")
    print(f"Kaldirilan: {len(sonuc['kaldirilan_ogeler'])}")

    if sonuc['yeni_ogeler']:
        print("\nYeni ogeler:")
        for o in sonuc['yeni_ogeler'][:10]:
            print(f"  + {o['baslik'][:70]}")
            print(f"    {o['tarih_str']}")

    print("\nBeyanname karsilastirmasi:")
    eslesmeyen = ogeleri_beyanname_ile_karsilastir(sonuc["yeni_ogeler"])
    if eslesmeyen:
        print(f"  {len(eslesmeyen)} oge bizde yok:")
        for o in eslesmeyen[:5]:
            print(f"  ! {o['baslik'][:70]}")
    else:
        print("  TUM ogeler eslesti veya yeni oge yok.")
