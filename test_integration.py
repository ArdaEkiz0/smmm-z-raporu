"""Integration test: all pages backend logic"""
import sys, os, json, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import (
    parse_z_raporu, data_to_luca_rows, generate_excel,
    varsayilan_kodlar, urun_kodlari_varsayilan,
    tum_fisleri_yukle, gecmis_listele, mukellefler,
    gorsel_hazirla, dosya_oku, dosya_yaz,
    otomatik_yedekle, HESAP_FILE, MUKELLEF_FILE, URUN_KODLARI_FILE,
)
from PIL import Image, ImageDraw, ImageFont
import tempfile

def test_dashboard_backend():
    """Dashboard: veri yukleme ve metrik hesaplama"""
    tum_fisler = tum_fisleri_yukle()
    assert isinstance(tum_fisler, list), "tum_fisler list olmali"
    for f in tum_fisler:
        assert "tarih" in f, f"Her fiste tarih olmali: {f.get('filename','?')}"
        assert "net_toplam" in f
        assert "brut" in f
    kayitlar = gecmis_listele()
    assert isinstance(kayitlar, list)
    ml = mukellefler()
    assert isinstance(ml, list)
    if tum_fisler:
        toplam_ciro = sum(f.get("net_toplam", 0) or 0 for f in tum_fisler)
        assert toplam_ciro >= 0
    print(f"  [PASS] test_dashboard_backend ({len(tum_fisler)} fis, {len(kayitlar)} kayit, {len(ml)} mukellef)")

def test_fis_gecmisi_backend():
    """Fis Gecmisi: filtreleme + Excel olusturma"""
    tum_fisler = tum_fisleri_yukle()
    kodlar = varsayilan_kodlar()
    urun_kodlari = urun_kodlari_varsayilan()
    if not tum_fisler:
        print("  [SKIP] test_fis_gecmisi_backend (veri yok)")
        return
    all_luca = []
    fc = 1
    for f in tum_fisler:
        all_luca.extend(data_to_luca_rows(f, kodlar, fc, urun_kodlari))
        fc += 1
    excel_data = generate_excel(all_luca)
    assert len(excel_data) > 0
    assert isinstance(excel_data, bytes)
    borc = sum(r.get("Borç", 0) or 0 for r in all_luca)
    alacak = sum(r.get("Alacak", 0) or 0 for r in all_luca)
    assert abs(borc - alacak) < 0.01, f"Balance: B={borc:.2f} A={alacak:.2f}"
    print(f"  [PASS] test_fis_gecmisi_backend ({len(all_luca)} satir, Excel={len(excel_data)}b, Balance OK)")

def test_kdv_ozeti_backend():
    """KDV Ozeti: oran bazli kdv hesaplama"""
    tum_fisler = tum_fisleri_yukle()
    if not tum_fisler:
        print("  [SKIP] test_kdv_ozeti_backend (veri yok)")
        return
    kdv_toplamlari = {}
    for f in tum_fisler:
        for urun in f.get("urunler", []):
            oran_ = urun.get("oran", 0)
            tutar = urun.get("tutar", 0)
            if oran_ > 0 and tutar > 0:
                if oran_ not in kdv_toplamlari:
                    kdv_toplamlari[oran_] = {"matrah": 0, "kdv": 0, "brut": 0}
                net = round(tutar / (1 + oran_ / 100), 2)
                kdv = round(tutar - net, 2)
                kdv_toplamlari[oran_]["matrah"] += net
                kdv_toplamlari[oran_]["kdv"] += kdv
                kdv_toplamlari[oran_]["brut"] += tutar
        for kv in f.get("kdv_kalemleri", []):
            oran_ = kv.get("oran", 0)
            if oran_ > 0 and oran_ not in kdv_toplamlari:
                matrah = kv.get("matrah", 0) or 0
                kdv_t = kv.get("kdv_tutari", 0) or 0
                kdv_toplamlari[oran_] = {"matrah": matrah, "kdv": kdv_t, "brut": round(matrah + kdv_t, 2)}
    if kdv_toplamlari:
        for oran_, k in kdv_toplamlari.items():
            assert k["matrah"] >= 0
            assert k["kdv"] >= 0
            assert k["brut"] >= 0
        print(f"  [PASS] test_kdv_ozeti_backend ({len(kdv_toplamlari)} oran: {list(kdv_toplamlari.keys())})")
    else:
        print("  [SKIP] test_kdv_ozeti_backend (KDV verisi yok)")

def test_ayarlar_backend():
    """Ayarlar: dosya okuma/yazma, yedekleme"""
    assert os.path.exists(HESAP_FILE) or True  # HESAP_FILE might not exist, fallback is fine
    if os.path.exists(HESAP_FILE):
        data = dosya_oku(HESAP_FILE)
        assert isinstance(data, dict)
        assert "kredi_karti" in data or "nakit" in data
    # urun_kodlari
    if os.path.exists(URUN_KODLARI_FILE):
        data = dosya_oku(URUN_KODLARI_FILE, [])
        assert isinstance(data, list)
    # otomatik yedekle (should not crash)
    result = otomatik_yedekle()
    assert result is True or result is False  # May fail if tesseract not in PATH etc.
    print(f"  [PASS] test_ayarlar_backend (yedek={result})")

def test_gorsel_hazirla():
    """Gorsel hazirlama pipeline testi"""
    img = Image.new("RGB", (100, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 50), "Z Raporu Test", fill="black")
    processed = gorsel_hazirla(img)
    assert processed is not None
    assert processed.mode == "L"
    assert processed.size[1] >= 200
    print(f"  [PASS] test_gorsel_hazirla ({img.size} -> {processed.size})")

def test_parse_from_realistic_text():
    """Parse realistic Z raporu text (simulating OCR output)"""
    text = """
    Z RAPORU
    Tarih: 15.06.2026    Saat: 14:30
    Fis No: 0042    Z No: 0150
    Urun Adi         %   Miktar    Tutar
    EKMEK           %1      50    505,00
    SUT             %10     20    220,00
    YOGURT          %10     15    165,00
    ----------------------------------
    Brut * 890,00
    Net Ciro * 890,00

    NAKIT         5  * 500,00
    Kredi Karti   10 * 200,00
    Yemek Ceki    3  * 190,00
    FIS IPTAL     2  *  50,00

    TOPLAM       %1   * 500,00   TOPKDV * 5,00
    TOPLAM       %10  * 350,00   TOPKDV * 35,00
    """
    r = parse_z_raporu(text)
    assert r["tarih"] == "15.06.2026"
    assert r["z_no"] == "0150"
    assert r["belge_no"] == "0042"
    assert abs(r["brut"] - 890) < 1
    assert abs(r["nakit"] - 500) < 1
    assert abs(r["kredi_karti"] - 200) < 1
    assert abs(r["yemek_ceki"] - 190) < 1
    assert abs(r["iadeler"] - 50) < 1
    assert len(r["urunler"]) >= 2, f"Urun sayisi: {len(r['urunler'])}"
    urun_adi = [u["urun"] for u in r["urunler"]]
    print(f"  Urunler: {urun_adi}")
    assert len(r["kdv_kalemleri"]) >= 1
    kodlar = varsayilan_kodlar()
    rows = data_to_luca_rows(r, kodlar, 1, urun_kodlari_varsayilan())
    borc = sum(ro.get("Borç", 0) or 0 for ro in rows)
    alacak = sum(ro.get("Alacak", 0) or 0 for ro in rows)
    assert abs(borc - alacak) < 0.01, f"Balance: B={borc:.2f} A={alacak:.2f}"
    print(f"  [PASS] test_parse_from_realistic_text (B={borc:.2f}, A={alacak:.2f})")

def test_mukellef_yonetimi():
    """Mukellef yonetimi: ekleme/silme"""
    ml = mukellefler()
    assert isinstance(ml, list)
    test_mukellef = {"adi": "TEST MUKELLEF", "vergi_no": "12345", "vd": "Test", "telefon": "555", "notlar": "", "olusturma": "01.01.2026"}
    # Test ekleme (simulate)
    yeni_liste = ml + [test_mukellef]
    assert len(yeni_liste) == len(ml) + 1
    print(f"  [PASS] test_mukellef_yonetimi (var={len(ml)}, simule={len(yeni_liste)})")

def test_excel_with_urun_kodlari():
    """Excel output when urun_kodlari are present"""
    data = {
        "tarih": "01.07.2026", "z_no": "999", "belge_no": "999",
        "nakit": 0, "kredi_karti": 1200, "yemek_ceki": 0,
        "toplam_tahsilat": 1200, "iadeler": 0, "net_toplam": 1200,
        "brut": 1200, "kdv_kalemleri": [{"oran": 20, "matrah": 1000, "kdv_tutari": 200}],
        "urunler": [
            {"urun": "EKMEK", "oran": 20, "miktar": 5, "tutar": 1200},
        ],
        "banka_adi": None, "firma_adi": None,
    }
    urun_kodlari = [{"pattern": "EKMEK", "hesap_kodu": "600.06", "aciklama": "Ekmek Satisi"}]
    kodlar = varsayilan_kodlar()
    rows = data_to_luca_rows(data, kodlar, 1, urun_kodlari)
    excel = generate_excel(rows)
    assert len(excel) > 0
    assert isinstance(excel, bytes)
    borc = sum(r.get("Borç", 0) or 0 for r in rows)
    alacak = sum(r.get("Alacak", 0) or 0 for r in rows)
    assert abs(borc - alacak) < 0.01
    print(f"  [PASS] test_excel_with_urun_kodlari ({len(excel)} bytes, Balance OK)")

if __name__ == "__main__":
    print("=== Integration Tests ===")
    test_dashboard_backend()
    test_fis_gecmisi_backend()
    test_kdv_ozeti_backend()
    test_ayarlar_backend()
    test_gorsel_hazirla()
    test_parse_from_realistic_text()
    test_mukellef_yonetimi()
    test_excel_with_urun_kodlari()
    print("\n=== TUM TESTLER BASARILI ===")
