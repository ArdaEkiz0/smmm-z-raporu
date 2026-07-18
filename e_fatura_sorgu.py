"""
E-Fatura mükellef sorgu + Nilvera API entegrasyonu.
GİB'in e-fatura mükellefiyet API'sini sorgular.
Nilvera PTT e-fatura/e-arşiv API entegrasyonu.
Kaynak: https://www.efatura.gov.tr, https://api.nilvera.com
Fallback: keyiflerolsun/eFatura paketi (PIP)
"""
import json
import os
import re
import time
from typing import Optional, Dict, List, Tuple

from config import NILVERA_FILE
from utils import log


def nilvera_config_yukle() -> Dict:
    """Nilvera API config yukle."""
    if os.path.exists(NILVERA_FILE):
        try:
            with open(NILVERA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            log.warning("Nilvera config yukleme hatasi", exc_info=True)
    return {"api_key": "", "base_url": "https://api.nilvera.com", "aktif": False}


def nilvera_config_kaydet(config: Dict) -> Dict:
    """Nilvera API config kaydet."""
    try:
        with open(NILVERA_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return {"basarili": True, "mesaj": "Nilvera API ayarları kaydedildi"}
    except Exception as e:
        return {"basarili": False, "mesaj": f"Hata: {e}"}


def vergi_no_dogrula(vkn_tckn: str) -> bool:
    """Vergi/TC kimlik no format kontrolü.
    VKN: 10 hane, TCKN: 11 hane. Sadece rakam."""
    if not vkn_tckn:
        return False
    vkn_tckn = re.sub(r"\D", "", str(vkn_tckn))
    if len(vkn_tckn) not in (10, 11):
        return False
    return True


def vkn_algo_dogrula(vkn: str) -> bool:
    """VKN (10 hane) algoritma dogrulamasi.
    Formül: (1,3,5,7,9. haneler * 8,6,4,2) + (2,4,6,8. haneler * 10,8,6,4) toplam
    mod 10 = 0 ise son hane 0, degilse 10 - (X mod 10).
    """
    vkn = re.sub(r"\D", "", str(vkn))
    if len(vkn) != 10:
        return False
    haneler = [int(d) for d in vkn]
    tek_toplam = haneler[0] * 8 + haneler[2] * 6 + haneler[4] * 4 + haneler[6] * 2
    cift_toplam = haneler[1] * 10 + haneler[3] * 8 + haneler[5] * 6 + haneler[7] * 4
    toplam = (tek_toplam + cift_toplam) % 10
    beklenen = 0 if toplam == 0 else 10 - toplam
    return haneler[9] == beklenen


def tckn_algo_dogrula(tckn: str) -> bool:
    """TCKN (11 hane) algoritma dogrulamasi."""
    tckn = re.sub(r"\D", "", str(tckn))
    if len(tckn) != 11 or tckn[0] == "0":
        return False
    haneler = [int(d) for d in tckn]
    tek_toplam = sum(haneler[i] for i in range(0, 9, 2))
    cift_toplam = sum(haneler[i] for i in range(1, 8, 2))
    onuncu_hane = (tek_toplam * 7 - cift_toplam) % 10
    if haneler[9] != onuncu_hane:
        return False
    toplam = sum(haneler[:10]) % 10
    return haneler[10] == toplam


def gib_efatura_sorgula(vkn: str, timeout: float = 10.0) -> Dict:
    """GİB e-fatura mükellef sorgusu.
    Returns: {"vkn", "efatura": bool, "earsiv": bool, "unvan": str, "kaynak": str, "hata": str|None}
    """
    sonuc = {
        "vkn": vkn,
        "efatura": False,
        "earsiv": False,
        "unvan": "",
        "kaynak": "GİB API",
        "hata": None,
    }

    if not vergi_no_dogrula(vkn):
        sonuc["hata"] = "Geçersiz VKN/TCKN formatı"
        return sonuc

    vkn_temiz = re.sub(r"\D", "", str(vkn))

    if len(vkn_temiz) == 10 and not vkn_algo_dogrula(vkn_temiz):
        sonuc["hata"] = "VKN algoritma doğrulaması başarısız"
        return sonuc
    if len(vkn_temiz) == 11 and not tckn_algo_dogrula(vkn_temiz):
        sonuc["hata"] = "TCKN algoritma doğrulaması başarısız"
        return sonuc

    try:
        import requests
        url = f"https://www.efatura.gov.tr/api/efatura/vkn/{vkn_temiz}"
        headers = {
            "User-Agent": "Mozilla/5.0 (SMMM-Z-Raporu/1.0)",
            "Accept": "application/json",
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            sonuc["efatura"] = bool(data.get("efaturaMukellef") or data.get("efatura"))
            sonuc["earsiv"] = bool(data.get("eArsivMukellef") or data.get("earsiv"))
            sonuc["unvan"] = data.get("unvan", "") or data.get("title", "")
            return sonuc
    except Exception as e:
        sonuc["kaynak"] = f"GİB API timeout/hata: {type(e).__name__}"
        sonuc["hata"] = str(e)[:100]

    sonuc["hata"] = sonuc["hata"] or "GİB API'den yanıt alınamadı. İnternet bağlantınızı kontrol edin."
    return sonuc


def toplu_sorgula(vkn_listesi: List[str], timeout: float = 10.0) -> List[Dict]:
    """Birden fazla VKN/TCKN icin sirayla sorgula."""
    sonuclar = []
    for vkn in vkn_listesi:
        sonuc = gib_efatura_sorgula(vkn, timeout=timeout)
        sonuclar.append(sonuc)
        time.sleep(0.3)
    return sonuclar


def sorgu_ozet(sonuc: Dict) -> str:
    """Sonuc dictini kullanici dostu stringe cevir."""
    if sonuc.get("hata"):
        return f"❌ {sonuc['hata']}"
    parts = []
    if sonuc.get("efatura"):
        parts.append("✅ E-Fatura mükellefi")
    else:
        parts.append("❌ E-Fatura mükellefi değil")
    if sonuc.get("earsiv"):
        parts.append("✅ E-Arşiv mükellefi")
    if sonuc.get("unvan"):
        parts.append(f"({sonuc['unvan']})")
    return " | ".join(parts)


# ── Nilvera API Fonksiyonlari ──────────────────────────────────────────

def nilvera_sorgula(vkn: str, timeout: float = 15.0) -> Dict:
    """Nilvera API ile VKN sorgusu.
    Returns: {"vkn", "efatura", "earsiv", "unvan", "kaynak", "hata", "vergi_dairesi", "adi_soyadi"}
    """
    config = nilvera_config_yukle()
    sonuc = {
        "vkn": vkn,
        "efatura": False,
        "earsiv": False,
        "unvan": "",
        "kaynak": "Nilvera API",
        "hata": None,
        "vergi_dairesi": "",
        "adi_soyadi": "",
    }

    if not config.get("api_key"):
        sonuc["hata"] = "Nilvera API anahtarı tanımlı değil. Ayarlar'dan girin."
        return sonuc

    if not vergi_no_dogrula(vkn):
        sonuc["hata"] = "Geçersiz VKN/TCKN formatı"
        return sonuc

    vkn_temiz = re.sub(r"\D", "", str(vkn))

    try:
        import requests
        base_url = config.get("base_url", "https://api.nilvera.com").rstrip("/")
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "SMMM-Z-Raporu/1.0",
        }

        url = f"{base_url}/Mukellef/Vkn/{vkn_temiz}"
        r = requests.get(url, headers=headers, timeout=timeout)

        if r.status_code == 200:
            data = r.json()
            sonuc["efatura"] = bool(data.get("eFatura") or data.get("efaturaMukellef"))
            sonuc["earsiv"] = bool(data.get("eArsiv") or data.get("eArsivMukellef"))
            sonuc["unvan"] = data.get("unvan", "") or data.get("adiSoyadi", "") or data.get("firmaAdi", "")
            sonuc["adi_soyadi"] = data.get("adiSoyadi", "")
            sonuc["vergi_dairesi"] = data.get("vergiDairesi", "")
        elif r.status_code == 401:
            sonuc["hata"] = "Nilvera API anahtarı geçersiz veya süresi dolmuş"
        elif r.status_code == 404:
            sonuc["hata"] = f"VKN {vkn_temiz} Nilvera'da bulunamadı"
        else:
            sonuc["hata"] = f"Nilvera API hata kodu: {r.status_code} - {r.text[:200]}"
    except Exception as e:
        sonuc["kaynak"] = f"Nilvera API hatası: {type(e).__name__}"
        sonuc["hata"] = str(e)[:200]

    return sonuc


def nilvera_toplu_sorgula(vkn_listesi: List[str], timeout: float = 15.0, progress_cb=None) -> List[Dict]:
    """Nilvera API ile toplu VKN sorgusu."""
    config = nilvera_config_yukle()
    if not config.get("api_key"):
        return [{"vkn": v, "hata": "Nilvera API anahtarı tanımlı değil", "kaynak": "Nilvera API"} for v in vkn_listesi]

    sonuclar = []
    toplam = len(vkn_listesi)
    for i, vkn in enumerate(vkn_listesi):
        sonuc = nilvera_sorgula(vkn, timeout=timeout)
        sonuclar.append(sonuc)
        if progress_cb:
            progress_cb(i + 1, toplam, sonuc)
        if i < toplam - 1:
            time.sleep(0.2)
    return sonuclar


def nilvera_fatura_listesi(vkn: str = None, baslangic: str = None, bitis: str = None,
                           durum: str = None, timeout: float = 15.0) -> Dict:
    """Nilvera'dan fatura listesi cek.
    durum: "Hepsi", "Taslak", "Onaylandi", "Iptal", "Reddedildi"
    Returns: {"faturalar": [...], "toplam": int, "hata": str|None}
    """
    config = nilvera_config_yukle()
    sonuc = {"faturalar": [], "toplam": 0, "hata": None}

    if not config.get("api_key"):
        sonuc["hata"] = "Nilvera API anahtarı tanımlı değil"
        return sonuc

    try:
        import requests
        base_url = config.get("base_url", "https://api.nilvera.com").rstrip("/")
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "SMMM-Z-Raporu/1.0",
        }

        params = {}
        if vkn:
            params["vkn"] = re.sub(r"\D", "", vkn)
        if baslangic:
            params["baslangicTarihi"] = baslangic
        if bitis:
            params["bitisTarihi"] = bitis
        if durum and durum != "Hepsi":
            params["durum"] = durum

        url = f"{base_url}/Fatura/Liste"
        r = requests.get(url, headers=headers, params=params, timeout=timeout)

        if r.status_code == 200:
            data = r.json()
            faturalar = data if isinstance(data, list) else data.get("faturalar", data.get("data", []))
            sonuc["faturalar"] = faturalar
            sonuc["toplam"] = len(faturalar)
        elif r.status_code == 401:
            sonuc["hata"] = "Nilvera API anahtarı geçersiz"
        else:
            sonuc["hata"] = f"Nilvera API hata: {r.status_code}"
    except Exception as e:
        sonuc["hata"] = str(e)[:200]

    return sonuc


def nilvera_fatura_detay(fatura_id: str, timeout: float = 15.0) -> Dict:
    """Nilvera'dan fatura detay cek."""
    config = nilvera_config_yukle()
    sonuc = {"fatura": None, "hata": None}

    if not config.get("api_key"):
        sonuc["hata"] = "Nilvera API anahtarı tanımlı değil"
        return sonuc

    try:
        import requests
        base_url = config.get("base_url", "https://api.nilvera.com").rstrip("/")
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "SMMM-Z-Raporu/1.0",
        }

        url = f"{base_url}/Fatura/{fatura_id}"
        r = requests.get(url, headers=headers, timeout=timeout)

        if r.status_code == 200:
            sonuc["fatura"] = r.json()
        elif r.status_code == 401:
            sonuc["hata"] = "Nilvera API anahtarı geçersiz"
        elif r.status_code == 404:
            sonuc["hata"] = f"Fatura bulunamadı: {fatura_id}"
        else:
            sonuc["hata"] = f"Nilvera API hata: {r.status_code}"
    except Exception as e:
        sonuc["hata"] = str(e)[:200]

    return sonuc


def nilvera_earsiv_indir(fatura_id: str, kayit_klasoru: str = None, timeout: float = 30.0) -> Dict:
    """Nilvera'dan e-arşiv PDF indir.
    Returns: {"dosya_yolu": str, "hata": str|None}
    """
    config = nilvera_config_yukle()
    sonuc = {"dosya_yolu": None, "hata": None}

    if not config.get("api_key"):
        sonuc["hata"] = "Nilvera API anahtarı tanımlı değil"
        return sonuc

    try:
        import requests
        base_url = config.get("base_url", "https://api.nilvera.com").rstrip("/")
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "User-Agent": "SMMM-Z-Raporu/1.0",
        }

        url = f"{base_url}/Fatura/{fatura_id}/Pdf"
        r = requests.get(url, headers=headers, timeout=timeout, stream=True)

        if r.status_code == 200:
            if kayit_klasoru is None:
                kayit_klasoru = os.path.join(os.path.dirname(os.path.abspath(__file__)), "earsiv_faturalar")
            os.makedirs(kayit_klasoru, exist_ok=True)
            dosya_yolu = os.path.join(kayit_klasoru, f"earsiv_{fatura_id}.pdf")
            with open(dosya_yolu, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            sonuc["dosya_yolu"] = dosya_yolu
        elif r.status_code == 401:
            sonuc["hata"] = "Nilvera API anahtarı geçersiz"
        elif r.status_code == 404:
            sonuc["hata"] = f"E-arşiv bulunamadı: {fatura_id}"
        else:
            sonuc["hata"] = f"Nilvera API hata: {r.status_code}"
    except Exception as e:
        sonuc["hata"] = str(e)[:200]

    return sonuc


def nilvera_fatura_olustur(fatura_veri: Dict, timeout: float = 30.0) -> Dict:
    """Nilvera üzerinden e-fatura/e-arşiv oluştur.
    fatura_veri: {
        "faturaTipi": "Earsiv" | "Efatura",
        "gonderenVkn": "VKN",
        "aliciVkn": "VKN",
        "aliciUnvani": "Firma Adı",
        "tarih": "YYYY-MM-DD",
        "paraBirimi": "TRY",
        "kalemler": [{"aciklama": "...", "miktar": 1, "birimFiyat": 100, "kdvOrani": 20, "tutar": 120}],
        "toplamTutar": 120,
        "kdvToplami": 20,
        "genelToplam": 140,
    }
    Returns: {"fatura_id": str, "hata": str|None}
    """
    config = nilvera_config_yukle()
    sonuc = {"fatura_id": None, "hata": None}

    if not config.get("api_key"):
        sonuc["hata"] = "Nilvera API anahtarı tanımlı değil"
        return sonuc

    try:
        import requests
        base_url = config.get("base_url", "https://api.nilvera.com").rstrip("/")
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "SMMM-Z-Raporu/1.0",
        }

        url = f"{base_url}/Fatura"
        r = requests.post(url, headers=headers, json=fatura_veri, timeout=timeout)

        if r.status_code in (200, 201):
            data = r.json()
            sonuc["fatura_id"] = data.get("faturaId") or data.get("id") or data.get("uuid")
        elif r.status_code == 401:
            sonuc["hata"] = "Nilvera API anahtarı geçersiz"
        elif r.status_code == 400:
            sonuc["hata"] = f"Geçersiz fatura verisi: {r.text[:200]}"
        else:
            sonuc["hata"] = f"Nilvera API hata: {r.status_code} - {r.text[:200]}"
    except Exception as e:
        sonuc["hata"] = str(e)[:200]

    return sonuc


def nilvera_fatura_gonder(fatura_id: str, timeout: float = 30.0) -> Dict:
    """Nilvera üzerinden fatura oluştur ve GİB'e gönder.
    Returns: {"basarili": bool, "durum": str, "hata": str|None}
    """
    config = nilvera_config_yukle()
    sonuc = {"basarili": False, "durum": "", "hata": None}

    if not config.get("api_key"):
        sonuc["hata"] = "Nilvera API anahtarı tanımlı değil"
        return sonuc

    try:
        import requests
        base_url = config.get("base_url", "https://api.nilvera.com").rstrip("/")
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "SMMM-Z-Raporu/1.0",
        }

        url = f"{base_url}/Fatura/{fatura_id}/Gonder"
        r = requests.post(url, headers=headers, timeout=timeout)

        if r.status_code == 200:
            data = r.json()
            sonuc["basarili"] = True
            sonuc["durum"] = data.get("durum", "Gönderildi")
        elif r.status_code == 401:
            sonuc["hata"] = "Nilvera API anahtarı geçersiz"
        elif r.status_code == 404:
            sonuc["hata"] = f"Fatura bulunamadı: {fatura_id}"
        else:
            sonuc["hata"] = f"Nilvera API hata: {r.status_code} - {r.text[:200]}"
    except Exception as e:
        sonuc["hata"] = str(e)[:200]

    return sonuc


def nilvera_fatura_iptal(fatura_id: str, aciklama: str = "", timeout: float = 30.0) -> Dict:
    """Nilvera üzerinden fatura iptal et.
    Returns: {"basarili": bool, "hata": str|None}
    """
    config = nilvera_config_yukle()
    sonuc = {"basarili": False, "hata": None}

    if not config.get("api_key"):
        sonuc["hata"] = "Nilvera API anahtarı tanımlı değil"
        return sonuc

    try:
        import requests
        base_url = config.get("base_url", "https://api.nilvera.com").rstrip("/")
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "SMMM-Z-Raporu/1.0",
        }

        url = f"{base_url}/Fatura/{fatura_id}/Iptal"
        payload = {"aciklama": aciklama} if aciklama else {}
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)

        if r.status_code == 200:
            sonuc["basarili"] = True
        elif r.status_code == 401:
            sonuc["hata"] = "Nilvera API anahtarı geçersiz"
        elif r.status_code == 404:
            sonuc["hata"] = f"Fatura bulunamadı: {fatura_id}"
        else:
            sonuc["hata"] = f"Nilvera API hata: {r.status_code} - {r.text[:200]}"
    except Exception as e:
        sonuc["hata"] = str(e)[:200]

    return sonuc


def nilvera_ozet(sonuc: Dict) -> str:
    """Nilvera sorgu sonucunu kullanici dostu stringe cevir."""
    if sonuc.get("hata"):
        return f"❌ {sonuc['hata']}"
    parts = []
    if sonuc.get("efatura"):
        parts.append("✅ E-Fatura")
    else:
        parts.append("❌ E-Fatura")
    if sonuc.get("earsiv"):
        parts.append("✅ E-Arşiv")
    if sonuc.get("unvan"):
        parts.append(f"({sonuc['unvan']})")
    if sonuc.get("adi_soyadi") and not sonuc.get("unvan"):
        parts.append(f"({sonuc['adi_soyadi']})")
    return " | ".join(parts)


def earsiv_pdf_temizle(en_fazla_gun: int = 30):
    """earsiv_faturalar/ klasorunde en_fazla_gun'den eski PDF'leri sil."""
    import glob
    from datetime import datetime, timedelta
    kayit_klasoru = os.path.join(os.path.dirname(os.path.abspath(__file__)), "earsiv_faturalar")
    if not os.path.exists(kayit_klasoru):
        return 0
    sinir = datetime.now() - timedelta(days=en_fazla_gun)
    silinen = 0
    for f in glob.glob(os.path.join(kayit_klasoru, "earsiv_*.pdf")):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(f))
            if mtime < sinir:
                os.remove(f)
                silinen += 1
        except Exception:
            log.warning("Eski earsiv PDF silinemedi", exc_info=True)
    if silinen > 0:
        log.info(f"{silinen} eski earsiv PDF temizlendi")
    return silinen
