"""
test_fis_uretici.py — Sentetik Z raporu ve fatura verisi uretir.

Testlerde kullanmak icin gercekci Z raporu metinleri olusturur.
Bilerek OCR hatalari eklenebilir (ogrenme sistemini test icin).
"""
import random
from datetime import datetime, timedelta
from typing import List, Optional


FIRMALAR = [
    "MİGROS", "BİM", "A101", "ŞOK", "CARREFOURSA",
    "METRO", "KIPA", "MADO", "STARBUCKS", "DOMINO'S",
    "MCDONALD'S", "BURGER KING", "TEKNOSA", "MEDIAMARKT",
    "KOÇTAŞ", "BAUHAUS", "LCWAIKIKI", "DERİMOD",
    "ZARA", "H&M", "ADİLE SULTAN MARKET",
]

BANKALAR = [
    "AKBANK", "GARANTİ BANKASI", "İŞ BANKASI",
    "YAPI KREDİ", "HALK BANK", "ZİRAAT BANKASI",
    "QNB FİNANSBANK", "VAKIFBANK",
]

URUNLER = [
    ("EKMEK", 10, 1), ("SÜT", 20, 10), ("YOĞURT", 15, 10),
    ("PEYNİR", 50, 10), ("ZEYTİN", 30, 10), ("YUMURTA", 25, 10),
    ("SİGARA", 60, 0), ("KOLA", 15, 20), ("SU", 5, 10),
    ("MAKARNA", 8, 10), ("PİRİNÇ", 20, 10), ("UN", 10, 10),
    ("ŞEKER", 15, 10), ("SIVI YAĞ", 25, 10), ("TEREYAĞ", 35, 10),
    ("SALAM", 20, 10), ("SOSİS", 18, 10), ("DOMATES", 10, 10),
    ("SALATALIK", 8, 10), ("BİBER", 12, 10),
]

MUK_FIRMALAR = [
    "MEHMET YILMAZ MARKET", "ALİ DEMİR BAKKALIYE",
    "AYŞE KAYA KURUYEMIS", "VEYSEL ŞAHİN TİCARET",
    "HASAN ÖZTÜRK GIDA", "FATMA YILDIZ TEKSTIL",
]


def _rastgele_firma() -> str:
    return random.choice(FIRMALAR)


def _rastgele_banka() -> str:
    return random.choice(BANKALAR)


def _rastgele_tarih(baslangic: str = "2024-01-01", bitis: str = "2024-12-31") -> str:
    bas = datetime.fromisoformat(baslangic)
    bit = datetime.fromisoformat(bitis)
    gun_farki = (bit - bas).days
    rast = bas + timedelta(days=random.randint(0, gun_farki))
    return rast.strftime("%d.%m.%Y")


def _rastgele_z_no() -> str:
    return str(random.randint(1, 99))


def _rastgele_fis_no() -> str:
    return str(random.randint(100, 9999))


def _birim_fiyatli_urun() -> dict:
    urun_adi, fiyat, kdv = random.choice(URUNLER)
    miktar = random.choice([1, 2, 3, 5, 10])
    toplam = round(miktar * fiyat, 2)
    return {"urun": urun_adi, "miktar": miktar, "birim_fiyat": fiyat, "tutar": toplam, "oran": kdv}


def _brut_hesapla(urunler: list) -> float:
    return round(sum(u["tutar"] for u in urunler), 2)


def z_raporu_metin_uret(firma: Optional[str] = None, tarih: Optional[str] = None,
                         z_no: Optional[str] = None, urun_sayisi: int = 3,
                         banka: Optional[str] = None,
                         ocr_hatali: bool = False) -> str:
    """Gercekci Z raporu metni uret.

    Args:
        ocr_hatali: True ise bilerek OCR hatalari eklenir (ogrenme testi icin)
    
    Returns:
        Z raporu ham metni (OCR ciktisi gibi)
    """
    firma = firma or _rastgele_firma()
    tarih = tarih or _rastgele_tarih()
    z_no = z_no or _rastgele_z_no()
    banka = banka or _rastgele_banka()

    # Urunler
    urunler = []
    for _ in range(urun_sayisi):
        urunler.append(_birim_fiyatli_urun())

    brut = _brut_hesapla(urunler)
    kdv_toplam = round(sum(u["tutar"] - (u["tutar"] / (1 + u["oran"]/100)) for u in urunler if u["oran"] > 0), 2)
    net = round(brut - kdv_toplam, 2) if kdv_toplam > 0 else brut

    nakit_oran = random.uniform(0.3, 0.8)
    nakit = round(brut * nakit_oran, 2)
    kk = round(brut - nakit, 2)

    # Z raporu metni
    satirlar = []
    satirlar.append(f"              {firma}")
    satirlar.append(f"              {banka}")
    satirlar.append(f"  Tarih: {tarih}  Saat: 15:30")
    satirlar.append(f"  Z NO: {z_no}")
    satirlar.append(f"  FİŞ NO: {_rastgele_fis_no()}")
    satirlar.append("-" * 40)
    satirlar.append("  ÜRÜN            MİKTAR  TUTAR")
    satirlar.append("-" * 40)

    for u in urunler:
        oran_str = f"%{u['oran']}" if u['oran'] > 0 else ""
        satirlar.append(f"  {u['urun']:<16} {u['miktar']:>3}  {u['tutar']:>8.2f}{oran_str:>4}")

    satirlar.append("-" * 40)
    satirlar.append(f"  BRÜT                 {brut:>8.2f}")
    if kdv_toplam > 0:
        satirlar.append(f"  TOPLAM KDV           {kdv_toplam:>8.2f}")
    satirlar.append(f"  NET TUTAR            {net:>8.2f}")
    satirlar.append("-" * 40)
    satirlar.append(f"  NAKİT                {nakit:>8.2f}")
    satirlar.append(f"  KREDİ KARTI İLE      {kk:>8.2f}")
    satirlar.append("-" * 40)
    satirlar.append(f"  TOPLAM TAHSİLAT      {brut:>8.2f}")
    satirlar.append("")
    satirlar.append("        TEŞEKKÜR EDERİZ")

    metin = "\n".join(satirlar)

    if ocr_hatali:
        metin = _ocr_hatasi_ekle(metin)

    return metin


def _ocr_hatasi_ekle(metin: str) -> str:
    """Bilerek OCR hatalari ekle (ogrenme sistemini test icin)."""
    hatalar = {
        "BRÜT": "BRUT",
        "NAKİT": "NAK1T",
        "KREDİ KARTI İLE": "KRED1 KARTI ILE",
        "TEŞEKKÜR": "TESEKKUR",
        "TOPLAM": "TOPLAN",
    }

    for dogru, yanlis in hatalar.items():
        if random.random() < 0.5:
            metin = metin.replace(dogru, yanlis, 1)

    return metin


def z_raporu_verisi_uret(firma: Optional[str] = None, tarih: Optional[str] = None,
                          z_no: Optional[str] = None, urun_sayisi: int = 3,
                          ocr_hatali: bool = False) -> dict:
    """Tam Z raporu verisi uret (parse_z_raporu ciktisi formatinda).
    
    Returns:
        {
            "tarih": "...", "z_no": "...", "firma_adi": "...", "banka_adi": "...",
            "brut": N, "net_toplam": N, "nakit": N, "kredi_karti": N,
            "yemek_ceki": 0, "iadeler": 0, "toplam_tahsilat": N,
            "urunler": [...], "kdv_kalemleri": [...], "ham_text": "...",
        }
    """
    if ocr_hatali:
        metin = z_raporu_metin_uret(firma, tarih, z_no, urun_sayisi, ocr_hatali=False)
        hata_metin = z_raporu_metin_uret(firma, tarih, z_no, urun_sayisi, ocr_hatali=True)
    else:
        metin = z_raporu_metin_uret(firma, tarih, z_no, urun_sayisi, ocr_hatali=False)
        hata_metin = ""

    firma = firma or _rastgele_firma()
    tarih = tarih or _rastgele_tarih()
    z_no = z_no or _rastgele_z_no()

    urunler = []
    for _ in range(urun_sayisi):
        urunler.append(_birim_fiyatli_urun())
    brut = _brut_hesapla(urunler)
    kdv_toplam = 0
    for u in urunler:
        if u["oran"] > 0:
            kdv_toplam += round(u["tutar"] - (u["tutar"] / (1 + u["oran"]/100)), 2)
    net = round(brut - kdv_toplam, 2) if kdv_toplam > 0 else brut

    nakit_oran = random.uniform(0.3, 0.8)
    nakit = round(brut * nakit_oran, 2)
    kk = round(brut - nakit, 2)

    from ocr import parse_z_raporu
    parsed = parse_z_raporu(metin) if metin else {}
    parsed["ham_text"] = hata_metin or metin

    return {
        "tarih": tarih,
        "z_no": z_no,
        "belge_no": "",
        "firma_adi": firma,
        "banka_adi": _rastgele_banka(),
        "brut": brut,
        "net_toplam": net,
        "nakit": nakit,
        "kredi_karti": kk,
        "yemek_ceki": 0.0,
        "iadeler": 0.0,
        "toplam_tahsilat": brut,
        "urunler": urunler,
        "kdv_kalemleri": [],
        "ham_text": metin,
        "_ground_truth": {
            "firma_adi": firma,
            "tarih": tarih,
            "z_no": z_no,
            "brut": brut,
            "net_toplam": net,
            "nakit": nakit,
            "kredi_karti": kk,
        },
    }
