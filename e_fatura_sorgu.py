"""
E-Fatura mükellef sorgu.
GİB'in e-fatura mükellefiyet API'sini sorgular.
Kaynak: https://www.efatura.gov.tr (resmi olmayan yöntem)
Fallback: keyiflerolsun/eFatura paketi (PIP)
"""
import re
import time
from typing import Optional, Dict, List, Tuple


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
