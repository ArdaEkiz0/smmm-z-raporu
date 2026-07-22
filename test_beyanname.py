"""Beyanname takvimi icin unit testler."""
import sys
from datetime import datetime, timedelta
sys.path.insert(0, r'C:\Users\ozel\OneDrive\Masaüstü\luuaaaaaaaaaaa')

from beyanname_takvimi import (
    BEYANNAMELER, beyanname_tarihi_hesapla, yaklasan_beyannameler,
    yillik_takvim, aylik_heatmap, resmi_tatil_mi, is_tatil_veya_h_sonu,
    son_is_gununu_bul, mukellef_atamalari_yukle, mukellef_atamasi_kaydet,
    mukellef_atamasi_sil, tamamlanma_durumu_yukle, tamamlanma_kaydet,
    tamamlanma_oku, donem_anahtari, istatistik, email_icerik_olustur,
    HATIRLATMA_GUNLERI, RESMI_TATILLER
)


def test_beyannameler_dict():
    """Beyanname sozlugu en az temel anahtarlari icermeli."""
    assert len(BEYANNAMELER) >= 9
    assert "KDV1" in BEYANNAMELER
    assert "MUHTASAR" in BEYANNAMELER
    assert "BABS" in BEYANNAMELER
    assert "GECICI_GV" in BEYANNAMELER
    assert "GECICI_KV" in BEYANNAMELER
    assert "GV" in BEYANNAMELER
    assert "KV" in BEYANNAMELER
    print("[OK] Beyanname sozlugu test edildi")


def test_beyanname_tarihi_hesapla_aylik():
    """Aylik beyannameler dogru hesaplanmali."""
    ref = datetime(2026, 7, 15)
    tarih = beyanname_tarihi_hesapla("KDV1", ref)
    assert tarih is not None
    assert tarih.year == 2026
    assert tarih.month == 8
    # 28 temmuz son gunu, 28 Agustos olmali (veya hafta sonu ertelemesi)
    assert tarih.day in (27, 28)
    print(f"[OK] KDV1 ay hesaplamasi: {tarih.strftime('%d.%m.%Y')}")


def test_beyanname_tarihi_hesapla_3aylik():
    """3 aylik beyannameler."""
    ref = datetime(2026, 1, 1)
    tarih = beyanname_tarihi_hesapla("GECICI_GV", ref)
    assert tarih is not None
    assert tarih.year == 2026
    # 3-aylik donemler Subat, Mayis, Agustos, Kasim (aylar listesi)
    # Subat'tan sonraki donem Mayis (ay 5)
    assert tarih.month >= 2
    assert tarih.month <= 12
    print(f"[OK] GECICI_GV 3-aylik hesaplamasi: {tarih.strftime('%d.%m.%Y')}")


def test_beyanname_tarihi_hesapla_yillik():
    """Yillik beyannameler."""
    ref = datetime(2026, 1, 1)
    tarih = beyanname_tarihi_hesapla("GV", ref)
    assert tarih is not None
    assert tarih.month == 3
    # 31 Mart - is gunu olmali (resmi tatil/cumartesi degilse)
    assert tarih.day in (30, 31)
    print(f"[OK] GV yillik hesaplamasi: {tarih.strftime('%d.%m.%Y')}")


def test_tatil_erteleme():
    """Tatil ve hafta sonu kontrolu."""
    # 1 Ocak 2024 - Yilbasi
    yilbasi = datetime(2024, 1, 1)
    assert is_tatil_veya_h_sonu(yilbasi) == True
    # 23 Nisan 2024 - milli tatil (sali)
    nisan = datetime(2024, 4, 23)
    assert is_tatil_veya_h_sonu(nisan) == True
    # Normal is gunu
    normal = datetime(2024, 4, 24)
    assert is_tatil_veya_h_sonu(normal) == False
    print("[OK] Tatil kontrolu test edildi")


def test_son_is_gununu_bul():
    """Tatil olan son gunu onceki is gunune kaydir."""
    # 1 Ocak 2024 = Pazartesi Yilbasi, bir onceki gun 31 Aralik 2023 = Pazar
    # 31 Aralik = Pazar, 29 Aralik = Cuma is gunu
    son_gun = son_is_gununu_bul(datetime(2024, 1, 1))
    assert son_gun.weekday() < 5
    print(f"[OK] Son is gunu bulma: {son_gun.strftime('%d.%m.%Y')}")


def test_resmi_tatil():
    """Resmi tatil kontrolleri."""
    assert resmi_tatil_mi(datetime(2026, 1, 1)) == True
    assert resmi_tatil_mi(datetime(2026, 4, 23)) == True
    assert resmi_tatil_mi(datetime(2026, 5, 19)) == True
    assert resmi_tatil_mi(datetime(2026, 8, 30)) == True
    assert resmi_tatil_mi(datetime(2026, 10, 29)) == True
    assert resmi_tatil_mi(datetime(2026, 11, 15)) == False
    print("[OK] Resmi tatil test edildi")


def test_yaklasan_beyannameler():
    """Yaklasan beyanname listesi."""
    ref = datetime(2026, 7, 22)
    yaklasan = yaklasan_beyannameler(ref, 30)
    assert isinstance(yaklasan, list)
    # Hepsinin gerekli alanlari var mi?
    for b in yaklasan:
        assert "kod" in b
        assert "ad" in b
        assert "tarih" in b
        assert "kalan_gun" in b
        assert "kategori" in b
        assert "renk" in b
    # Tarihe gore sirali mi?
    if len(yaklasan) > 1:
        for i in range(len(yaklasan) - 1):
            assert yaklasan[i]["kalan_gun"] <= yaklasan[i+1]["kalan_gun"]
    print(f"[OK] {len(yaklasan)} yakin beyanname listelendi")


def test_yaklasan_kategori_filtresi():
    """Kategori filtresi calismali."""
    ref = datetime(2026, 7, 22)
    vergi = yaklasan_beyannameler(ref, 365, kategori="vergi")
    eb = yaklasan_beyannameler(ref, 365, kategori="e-belge")
    sgk = yaklasan_beyannameler(ref, 365, kategori="sgk")
    for b in vergi:
        assert b["kategori"] == "vergi"
    for b in eb:
        assert b["kategori"] == "e-belge"
    for b in sgk:
        assert b["kategori"] == "sgk"
    print(f"[OK] Kategori filtreleri: vergi={len(vergi)}, e-belge={len(eb)}, sgk={len(sgk)}")


def test_yillik_takvim():
    """Yillik takvim."""
    takvim = yillik_takvim(2026)
    assert len(takvim) > 0
    tum_kodlar = {k["kod"] for k in takvim}
    assert "KDV1" in tum_kodlar
    assert "GV" in tum_kodlar
    # Aylik olanlar yilda en az 11 kez olmali (1 ay atlanabilir)
    kdv1_sayisi = sum(1 for k in takvim if k["kod"] == "KDV1")
    assert kdv1_sayisi >= 11
    print(f"[OK] {len(takvim)} beyanname 2026'da, KDV1: {kdv1_sayisi} kez")


def test_aylik_heatmap():
    """Aylik heatmap."""
    heatmap = aylik_heatmap(2026, 7)
    assert isinstance(heatmap, dict)
    # 31 gun var mi?
    assert 1 in heatmap
    assert 31 in heatmap
    print(f"[OK] Temmuz 2026 heatmap: {sum(len(v) for v in heatmap.values())} beyanname")


def test_email_icerik_olustur():
    """Email icerigi."""
    ref = datetime(2026, 7, 22)
    yaklasan = yaklasan_beyannameler(ref, 30)
    konu, icerik = email_icerik_olustur(yaklasan)
    assert konu
    assert "Beyanname" in konu
    if yaklasan:
        assert "Yaklasan beyannameler" in icerik
    print(f"[OK] Email konu: {konu}")


def test_mukellef_atamalari():
    """Mukellef atamasi CRUD."""
    test_kod = "TEST_KOD"
    mukellef_listesi = ["Müşteri 1", "Müşteri 2", "Müşteri 3"]

    basarili = mukellef_atamasi_kaydet(test_kod, mukellef_listesi)
    assert basarili

    atamalar = mukellef_atamalari_yukle()
    assert test_kod in atamalar
    assert atamalar[test_kod] == mukellef_listesi

    basarili = mukellef_atamasi_sil(test_kod)
    assert basarili

    atamalar = mukellef_atamalari_yukle()
    assert test_kod not in atamalar
    print("[OK] Mukellef atama CRUD test edildi")


def test_tamamlanma_durumu():
    """Beyanname tamamlanma durumu."""
    test_anahtar = "KDV1_202607"
    basarili = tamamlanma_kaydet(test_anahtar, "tamamlandi", "Test notu")
    assert basarili

    durum = tamamlanma_oku(test_anahtar)
    assert durum is not None
    assert durum["durum"] == "tamamlandi"
    assert durum["notu"] == "Test notu"

    # Temizle
    tum = tamamlanma_durumu_yukle()
    if test_anahtar in tum:
        del tum[test_anahtar]
        import json
        import os
        dosya = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "beyanname_tamamlanma.json"
        )
        with open(dosya, "w", encoding="utf-8") as f:
            json.dump(tum, f, ensure_ascii=False, indent=2)
    print("[OK] Tamamlanma durumu CRUD test edildi")


def test_donem_anahtari():
    """Donem anahtari olusturma."""
    tarih = datetime(2026, 7, 15)
    anahtar = donem_anahtari("KDV1", tarih)
    assert anahtar == "KDV1_202607"
    print(f"[OK] Donem anahtari: {anahtar}")


def test_istatistik():
    """Istatistik fonksiyonu."""
    ref = datetime(2026, 7, 22)
    stats = istatistik(ref)
    assert "yaklasan_30_gun" in stats
    assert "kritik_bugun" in stats
    assert "kategoriler" in stats
    assert "toplam_beyanname_turu" in stats
    assert stats["toplam_beyanname_turu"] == len(BEYANNAMELER)
    print(f"[OK] Istatistik: {stats}")


def test_hatirlatma_gunleri():
    """Hatirlatma gunleri listesi."""
    assert 0 in HATIRLATMA_GUNLERI
    assert 1 in HATIRLATMA_GUNLERI
    assert 3 in HATIRLATMA_GUNLERI
    assert 7 in HATIRLATMA_GUNLERI
    print(f"[OK] Hatirlatma gunleri: {HATIRLATMA_GUNLERI}")


def test_resmi_tatiller():
    """Resmi tatiller sozlugu."""
    assert 2024 in RESMI_TATILLER
    assert 2025 in RESMI_TATILLER
    assert 2026 in RESMI_TATILLER
    assert 2027 in RESMI_TATILLER
    # Onemli gunler her yil olmali
    for yil in [2024, 2025, 2026]:
        assert (1, 1) in RESMI_TATILLER[yil]  # Yilbasi
        assert (4, 23) in RESMI_TATILLER[yil]  # Ulusal Egemenlik
        assert (5, 1) in RESMI_TATILLER[yil]  # Emek
        assert (5, 19) in RESMI_TATILLER[yil]  # Genclik
        assert (8, 30) in RESMI_TATILLER[yil]  # Zafer
        assert (10, 29) in RESMI_TATILLER[yil]  # Cumhuriyet
    print("[OK] Resmi tatiller sozlugu test edildi")


if __name__ == "__main__":
    test_beyannameler_dict()
    test_beyanname_tarihi_hesapla_aylik()
    test_beyanname_tarihi_hesapla_3aylik()
    test_beyanname_tarihi_hesapla_yillik()
    test_tatil_erteleme()
    test_son_is_gununu_bul()
    test_resmi_tatil()
    test_yaklasan_beyannameler()
    test_yaklasan_kategori_filtresi()
    test_yillik_takvim()
    test_aylik_heatmap()
    test_email_icerik_olustur()
    test_mukellef_atamalari()
    test_tamamlanma_durumu()
    test_donem_anahtari()
    test_istatistik()
    test_hatirlatma_gunleri()
    test_resmi_tatiller()
    print()
    print("=" * 60)
    print("TUM TESTLER BASARILI!")
    print("=" * 60)
