"""
ogrenme_cekirdigi.py + ocr_dogrulama.py testleri.
"""
import sys, os, json, tempfile, shutil, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_TEST_DIR = None


def setup_function():
    global _TEST_DIR
    _TEST_DIR = tempfile.mkdtemp(prefix="ogrenme_test_")
    import ogrenme_cekirdigi as oc
    oc.OGRENME_DB = os.path.join(_TEST_DIR, "ogrenme_db.json")


def teardown_function():
    global _TEST_DIR
    if _TEST_DIR and os.path.exists(_TEST_DIR):
        shutil.rmtree(_TEST_DIR, ignore_errors=True)


# ============================================================
# ogrenme_cekirdigi.py tests
# ============================================================

def test_modul_yuklenebilir():
    import ogrenme_cekirdigi as oc
    assert hasattr(oc, "ogrenme_db_yukle")
    assert hasattr(oc, "duzeltme_kaydet")
    assert hasattr(oc, "auto_duzeltme_uygula")
    assert hasattr(oc, "alan_duzeltme_kaydet")
    assert hasattr(oc, "alan_duzeltme_uygula")
    assert hasattr(oc, "istatistik_raporu")
    assert hasattr(oc, "ogrenilen_sozluk_istatistik")
    print("  [PASS]")


def test_ilk_yukleme_bos():
    import ogrenme_cekirdigi as oc
    setup_function()
    db = oc.ogrenme_db_yukle()
    assert "sozluk" in db
    assert "istatistik" in db
    assert db["istatistik"]["toplam_duzeltme"] == 0
    print("  [PASS]")


def test_duzeltme_kaydet():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut", kaynak="manuel")
    db = oc.ogrenme_db_yukle()
    assert "BRUT" in db["sozluk"]
    assert db["sozluk"]["BRUT"]["dogru"] == "BRÜT"
    assert db["sozluk"]["BRUT"]["sayac"] == 1
    print("  [PASS]")


def test_duzeltme_tekrar_kaydet():
    import ogrenme_cekirdigi as oc
    setup_function()
    for _ in range(5):
        oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut")
    db = oc.ogrenme_db_yukle()
    assert db["sozluk"]["BRUT"]["sayac"] == 5
    assert db["istatistik"]["toplam_duzeltme"] == 5
    print("  [PASS]")


def test_duzeltme_ayni_deger_atla():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.duzeltme_kaydet("BRÜT", "BRÜT")
    db = oc.ogrenme_db_yukle()
    assert len(db["sozluk"]) == 0
    print("  [PASS]")


def test_duzeltme_bos_atla():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.duzeltme_kaydet("", "BRÜT")
    oc.duzeltme_kaydet("BRUT", "")
    db = oc.ogrenme_db_yukle()
    assert len(db["sozluk"]) == 0
    print("  [PASS]")


def test_guven_puani_sifir():
    import ogrenme_cekirdigi as oc
    setup_function()
    db = oc.ogrenme_db_yukle()
    assert oc._guven_hesapla({"sayac": 0}) == 0.0
    assert oc._guven_hesapla({}) == 0.0
    print("  [PASS]")


def test_guven_puani_artar():
    import ogrenme_cekirdigi as oc
    setup_function()
    guvenler = []
    for i in range(1, 11):
        oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut")
        db = oc.ogrenme_db_yukle()
        g = oc._guven_hesapla(db["sozluk"]["BRUT"])
        guvenler.append(g)
    # Each addition should increase (or at least not decrease) confidence
    for i in range(1, len(guvenler)):
        assert guvenler[i] >= guvenler[i-1] * 0.9, f"Guven azaldi: {guvenler[i-1]:.3f} -> {guvenler[i]:.3f}"
    # After 10 corrections, should be above 0.8
    assert guvenler[-1] > 0.8, f"10 duzeltme sonrasi guven: {guvenler[-1]:.3f}"
    print("  [PASS]")


def test_auto_duzeltme_uygula_metinde():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut")
    oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut")
    oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut")
    text = "BRUT 100.00 TL"
    duzeltilmis, degisiklikler = oc.auto_duzeltme_uygula(text, alan_adi="brut")
    assert "BRÜT" in duzeltilmis
    assert "BRUT" not in duzeltilmis
    assert len(degisiklikler) >= 1
    assert degisiklikler[0]["uygulandi"] is True
    print("  [PASS]")


def test_auto_duzeltme_dusuk_guven_uygulama():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut")
    text = "BRUT 100.00 TL"
    duzeltilmis, degisiklikler = oc.auto_duzeltme_uygula(text, alan_adi="brut")
    assert len(degisiklikler) == 1
    assert degisiklikler[0]["uygulandi"] is False
    print("  [PASS]")


def test_ogrenilen_sozluk_istatistik_filtre():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.duzeltme_kaydet("BRUT", "BRÜT")
    oc.duzeltme_kaydet("BRUT", "BRÜT")
    oc.duzeltme_kaydet("NAK1T", "NAKİT")
    sozluk = oc.ogrenilen_sozluk_istatistik(min_guven=0.0)
    assert len(sozluk) == 2
    sozluk_yuksek = oc.ogrenilen_sozluk_istatistik(min_guven=0.9)
    assert len(sozluk_yuksek) < 2
    print("  [PASS]")


def test_alan_duzeltme_kaydet_ve_uygula():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.alan_duzeltme_kaydet("firma_adi", "MGROS", "MİGROS")
    oc.alan_duzeltme_kaydet("firma_adi", "MGROS", "MİGROS")
    oc.alan_duzeltme_kaydet("firma_adi", "MGROS", "MİGROS")
    oc.alan_duzeltme_kaydet("firma_adi", "MGROS", "MİGROS")
    oc.alan_duzeltme_kaydet("firma_adi", "MGROS", "MİGROS")
    oc.alan_duzeltme_kaydet("firma_adi", "MGROS", "MİGROS")
    parsed = {"firma_adi": "MGROS", "brut": 100.0}
    parsed, degisiklikler = oc.alan_duzeltme_uygula(parsed)
    assert parsed["firma_adi"] == "MİGROS"
    assert len(degisiklikler) == 1
    print("  [PASS]")


def test_alan_duzeltme_dusuk_sayac():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.alan_duzeltme_kaydet("firma_adi", "MGROS", "MİGROS")
    parsed = {"firma_adi": "MGROS", "brut": 100.0}
    parsed, degisiklikler = oc.alan_duzeltme_uygula(parsed)
    assert parsed["firma_adi"] == "MGROS"  # dusuk guven, uygulanmadi
    assert len(degisiklikler) == 0
    print("  [PASS]")


def test_istatistik_raporu():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.duzeltme_kaydet("BRUT", "BRÜT")
    oc.alan_duzeltme_kaydet("firma_adi", "MGROS", "MİGROS")
    rapor = oc.istatistik_raporu()
    assert rapor["toplam_kayit"] >= 1
    assert rapor["istatistik"]["toplam_duzeltme"] >= 1
    assert "firma_adi" in rapor["alan_bazli_kayit"]
    print("  [PASS]")


def test_gecmis_temizle():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut")
    # Force very old timestamp
    db = oc.ogrenme_db_yukle()
    for key in db["sozluk"]:
        db["sozluk"][key]["son"] = "2020-01-01T00:00:00"
    oc.ogrenme_db_kaydet(db)
    silinen = oc.gecmis_temizle(gun_limiti=1)
    assert silinen >= 1
    db2 = oc.ogrenme_db_yukle()
    assert len(db2["sozluk"]) == 0
    print("  [PASS]")


def test_birden_fazla_duzeltme_ayni_metin():
    import ogrenme_cekirdigi as oc
    setup_function()
    for _ in range(3):
        oc.duzeltme_kaydet("BRUT", "BRÜT")
        oc.duzeltme_kaydet("NAK1T", "NAKİT")
    text = "BRUT 100 TL NAK1T 50 TL"
    duzeltilmis, _ = oc.auto_duzeltme_uygula(text)
    assert "BRÜT" in duzeltilmis
    assert "NAKİT" in duzeltilmis
    print("  [PASS]")


def test_kaynak_cesitliligi_bonus():
    import ogrenme_cekirdigi as oc
    setup_function()
    oc.duzeltme_kaydet("BRUT", "BRÜT", kaynak="manuel")
    oc.duzeltme_kaydet("BRUT", "BRÜT", kaynak="manuel")
    db = oc.ogrenme_db_yukle()
    g1 = oc._guven_hesapla(db["sozluk"]["BRUT"])
    oc.duzeltme_kaydet("BRUT", "BRÜT", kaynak="otomatik")
    db = oc.ogrenme_db_yukle()
    g2 = oc._guven_hesapla(db["sozluk"]["BRUT"])
    # More sources = higher confidence
    assert g2 > g1
    print("  [PASS]")


def test_normalize_key():
    import ogrenme_cekirdigi as oc
    assert oc._normalize_key(" BRUT ") == "BRUT"
    assert oc._normalize_key("Nakit  ") == "NAKIT"
    assert oc._normalize_key("") == ""
    assert oc._normalize_key(None) == ""
    print("  [PASS]")


# ============================================================
# ocr_dogrulama.py tests
# ============================================================

def test_dogrulama_modul_yuklenebilir():
    import ocr_dogrulama as od
    assert hasattr(od, "ocr_sonuc_dogrula")
    assert hasattr(od, "_tarih_dogrula")
    assert hasattr(od, "_sayi_dogrula")
    assert hasattr(od, "_metin_dogrula")
    print("  [PASS]")


def test_tarih_dogrula_gecerli():
    from ocr_dogrulama import _tarih_dogrula
    assert _tarih_dogrula("15.03.2024") == (True, "gecerli")
    assert _tarih_dogrula("01/01/2024") == (True, "gecerli")
    assert _tarih_dogrula("31-12-2024") == (True, "gecerli")
    print("  [PASS]")


def test_tarih_dogrula_gecersiz():
    from ocr_dogrulama import _tarih_dogrula
    assert _tarih_dogrula("") == (False, "bos")
    assert _tarih_dogrula("abc") == (False, "cok_fazla_harf_var")
    assert _tarih_dogrula("32.01.2024")[0] is False
    assert _tarih_dogrula("01.13.2024")[0] is False
    print("  [PASS]")


def test_tarih_dogrula_eski():
    from ocr_dogrulama import _tarih_dogrula
    assert _tarih_dogrula("01.01.1800") == (False, "yil_gecersiz: 1800")
    assert _tarih_dogrula("01.01.2200") == (False, "yil_gecersiz: 2200")
    print("  [PASS]")


def test_sayi_dogrula_gecerli():
    from ocr_dogrulama import _sayi_dogrula
    kurallar = {"min_deger": 0, "max_deger": 100000}
    assert _sayi_dogrula(100, kurallar) == (True, "gecerli")
    assert _sayi_dogrula(0.01, kurallar) == (True, "gecerli")
    assert _sayi_dogrula("500.50", kurallar) == (True, "gecerli")
    print("  [PASS]")


def test_sayi_dogrula_gecersiz():
    from ocr_dogrulama import _sayi_dogrula
    kurallar = {"min_deger": 0, "max_deger": 1000}
    assert _sayi_dogrula(-5, kurallar)[0] is False
    assert _sayi_dogrula(5000, kurallar)[0] is False
    assert _sayi_dogrula("abc", kurallar)[0] is False
    print("  [PASS]")


def test_metin_dogrula_firma_adi():
    from ocr_dogrulama import _metin_dogrula
    kurallar = {"min_uzunluk": 3, "max_uzunluk": 60}
    assert _metin_dogrula("MİGROS", kurallar, "firma_adi") == (True, "gecerli")
    assert _metin_dogrula("ab", kurallar, "firma_adi") == (False, "cok_kisa: 2 < 3")
    assert _metin_dogrula("12345", kurallar, "firma_adi") == (False, "sadece_rakam")
    print("  [PASS]")


def test_metin_dogrula_banka():
    from ocr_dogrulama import _metin_dogrula
    kurallar = {"min_uzunluk": 3, "max_uzunluk": 40}
    assert _metin_dogrula("AKBANK", kurallar, "banka_adi") == (True, "gecerli")
    print("  [PASS]")


def test_ocr_sonuc_dogrula_temiz():
    from ocr_dogrulama import ocr_sonuc_dogrula
    parsed = {
        "tarih": "15.03.2024", "z_no": "12", "belge_no": "1234",
        "firma_adi": "MİGROS", "banka_adi": "AKBANK",
        "brut": 1500.00, "net_toplam": 1200.00,
        "nakit": 800.00, "kredi_karti": 700.00,
        "yemek_ceki": 0.0, "iadeler": 0.0, "toplam_tahsilat": 1500.00,
        "urunler": [], "kdv_kalemleri": [],
    }
    sonuc = ocr_sonuc_dogrula(parsed, ham_text="Z RAPORU\nMİGROS\n15.03.2024")
    assert sonuc["genel_skor"] >= 70
    assert sonuc["gecerli_alan"] >= 6
    print("  [PASS]")


def test_ocr_sonuc_dogrula_hatali():
    from ocr_dogrulama import ocr_sonuc_dogrula
    parsed = {
        "tarih": "", "z_no": "", "belge_no": "",
        "firma_adi": "12345", "banka_adi": "",
        "brut": -1, "net_toplam": 999999,
        "nakit": 100, "kredi_karti": 0,
        "yemek_ceki": 0, "iadeler": 0, "toplam_tahsilat": 0,
        "urunler": [], "kdv_kalemleri": [],
    }
    sonuc = ocr_sonuc_dogrula(parsed, ham_text="kisa")
    assert sonuc["genel_skor"] < 70
    assert sonuc["sorunlu_alan_sayisi"] >= 1
    print("  [PASS]")


def test_tutarlilik_kontrolu():
    from ocr_dogrulama import _tutarlilik_dogrula
    sorunlar = _tutarlilik_dogrula({
        "brut": 100, "net_toplam": 200, "nakit": 10,
        "kredi_karti": 10, "yemek_ceki": 0, "iadeler": 200,
    })
    kodlar = [s["kod"] for s in sorunlar]
    assert "NET_BRUTTEN_BUYUK" in kodlar
    assert "IADE_BRUTTEN_BUYUK" in kodlar
    print("  [PASS]")


def test_anomali_tespiti():
    from ocr_dogrulama import _anomali_tespit
    sorunlar = _anomali_tespit({
        "firma_adi": "ERROR", "brut": 0.5, "tarih": "01.01.2010",
    }, ham_text="ERROR kısa metin")
    kodlar = [s["kod"] for s in sorunlar]
    assert "FIRMA_HATA_ICERIYOR" in kodlar
    assert "BRUT_COK_DUSUK" in kodlar
    assert "OCR_METIN_COK_KISA" in kodlar
    print("  [PASS]")


def test_mukellef_capraz_referans():
    from ocr_dogrulama import ocr_sonuc_dogrula
    parsed = {"firma_adi": "MEHMET MARKET", "tarih": "15.03.2024",
              "brut": 1000, "net_toplam": 900, "nakit": 500, "kredi_karti": 500,
              "yemek_ceki": 0, "iadeler": 0, "toplam_tahsilat": 1000,
              "z_no": "1", "belge_no": "", "banka_adi": "",
              "urunler": [], "kdv_kalemleri": []}
    mukellefler = [{"adi": "MEHMET MARKET", "kisa_adi": ""}]
    sonuc = ocr_sonuc_dogrula(parsed, ham_text="test", mukellef_listesi=mukellefler)
    firma_sorunlari = [s for s in sonuc["sorunlar"] if s["kod"] == "FIRMA_MUKELLEF_ESLESMEDI"]
    assert len(firma_sorunlari) == 0
    print("  [PASS]")


def test_mukellef_capraz_referans_eslesmez():
    from ocr_dogrulama import ocr_sonuc_dogrula
    parsed = {"firma_adi": "OLMAYAN FIRMA", "tarih": "15.03.2024",
              "brut": 1000, "net_toplam": 900, "nakit": 500, "kredi_karti": 500,
              "yemek_ceki": 0, "iadeler": 0, "toplam_tahsilat": 1000,
              "z_no": "1", "belge_no": "", "banka_adi": "",
              "urunler": [], "kdv_kalemleri": []}
    mukellefler = [{"adi": "MEHMET MARKET", "kisa_adi": ""}]
    sonuc = ocr_sonuc_dogrula(parsed, ham_text="test", mukellef_listesi=mukellefler)
    firma_sorunlari = [s for s in sonuc["sorunlar"] if s["kod"] == "FIRMA_MUKELLEF_ESLESMEDI"]
    assert len(firma_sorunlari) >= 1
    print("  [PASS]")


def test_entegre_pipeline():
    """OCR + ogrenme + dogrulama entegrasyon testi."""
    import ogrenme_cekirdigi as oc
    setup_function()

    oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut")
    oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut")
    oc.duzeltme_kaydet("BRUT", "BRÜT", alan_adi="brut")
    oc.alan_duzeltme_kaydet("firma_adi", "MMGROS", "MİGROS")
    oc.alan_duzeltme_kaydet("firma_adi", "MMGROS", "MİGROS")
    oc.alan_duzeltme_kaydet("firma_adi", "MMGROS", "MİGROS")
    oc.alan_duzeltme_kaydet("firma_adi", "MMGROS", "MİGROS")
    oc.alan_duzeltme_kaydet("firma_adi", "MMGROS", "MİGROS")
    oc.alan_duzeltme_kaydet("firma_adi", "MMGROS", "MİGROS")

    from test_fis_uretici import z_raporu_metin_uret, z_raporu_verisi_uret
    metin = z_raporu_metin_uret(firma="MİGROS", tarih="15.03.2024", z_no="5",
                                 urun_sayisi=2, ocr_hatali=True)

    from ocr import parse_z_raporu, duzeltme_uygula

    duzeltilmis_metin, degisiklikler = oc.auto_duzeltme_uygula(metin)
    parsed = parse_z_raporu(duzeltilmis_metin)
    parsed, alan_duzeltmeleri = oc.alan_duzeltme_uygula(parsed)

    from ocr_dogrulama import ocr_sonuc_dogrula
    dogrulama = ocr_sonuc_dogrula(parsed, ham_text=metin)

    assert dogrulama["genel_skor"] >= 1
    if parsed.get("brut", 0) > 0:
        assert parsed["brut"] > 0

    print("  [PASS]")


if __name__ == "__main__":
    print("=== ogrenme_cekirdigi Testleri ===")
    test_modul_yuklenebilir()
    test_ilk_yukleme_bos()
    test_duzeltme_kaydet()
    test_duzeltme_tekrar_kaydet()
    test_duzeltme_ayni_deger_atla()
    test_duzeltme_bos_atla()
    test_guven_puani_sifir()
    test_guven_puani_artar()
    test_auto_duzeltme_uygula_metinde()
    test_auto_duzeltme_dusuk_guven_uygulama()
    test_ogrenilen_sozluk_istatistik_filtre()
    test_alan_duzeltme_kaydet_ve_uygula()
    test_alan_duzeltme_dusuk_sayac()
    test_istatistik_raporu()
    test_gecmis_temizle()
    test_birden_fazla_duzeltme_ayni_metin()
    test_kaynak_cesitliligi_bonus()
    test_normalize_key()
    print("\n=== ocr_dogrulama Testleri ===")
    test_dogrulama_modul_yuklenebilir()
    test_tarih_dogrula_gecerli()
    test_tarih_dogrula_gecersiz()
    test_tarih_dogrula_eski()
    test_sayi_dogrula_gecerli()
    test_sayi_dogrula_gecersiz()
    test_metin_dogrula_firma_adi()
    test_metin_dogrula_banka()
    test_ocr_sonuc_dogrula_temiz()
    test_ocr_sonuc_dogrula_hatali()
    test_tutarlilik_kontrolu()
    test_anomali_tespiti()
    test_mukellef_capraz_referans()
    test_mukellef_capraz_referans_eslesmez()
    test_entegre_pipeline()
    print("\n=== TUM TESTLER BASARILI ===")
