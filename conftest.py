"""
pytest conftest.py - Paylasilan fixture'lar ve test konfigürasyonu.
"""
import os
import sys
import tempfile
import shutil
import json
import pytest

# Proje kokunu Python path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def test_data_dir():
    """Tum test boyunca kullanilacak gecici veri dizini."""
    tmpdir = tempfile.mkdtemp(prefix="smmm_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_dir():
    """Her test icin ayri gecici dizin."""
    tmpdir = tempfile.mkdtemp(prefix="smmm_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def mock_config(temp_dir, monkeypatch):
    """config modülündeki dosya yollarini gecici dizine yonlendir."""
    import config

    mapping = {
        "AUTH_FILE": os.path.join(temp_dir, "auth_config.json"),
        "HESAP_FILE": os.path.join(temp_dir, "hesap_kodlari.json"),
        "MUKELLEF_FILE": os.path.join(temp_dir, "mukellefler.json"),
        "GECMIS_KLASORU": os.path.join(temp_dir, "gecmis"),
        "FISLER_KLASORU": os.path.join(temp_dir, "fisler"),
        "YEDEK_KLASORU": os.path.join(temp_dir, "yedekler"),
        "URUN_KODLARI_FILE": os.path.join(temp_dir, "urun_kodlari.json"),
        "SABLON_FILE": os.path.join(temp_dir, "luca_sablonu.xlsx"),
        "EMAIL_FILE": os.path.join(temp_dir, "email_config.json"),
        "DUZELTME_SOZLUK": os.path.join(temp_dir, "duzeltme_sozlugu.json"),
        "OGRENILEN_SOZLUK": os.path.join(temp_dir, "ogrenilen_sozluk.json"),
        "OGRENILEN_ALANLAR": os.path.join(temp_dir, "ogrenilen_alanlar.json"),
    }

    for attr, path in mapping.items():
        if hasattr(config, attr):
            monkeypatch.setattr(config, attr, path)

    # Gerekli dizinleri olustur
    os.makedirs(os.path.join(temp_dir, "gecmis"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "fisler"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "yedekler"), exist_ok=True)

    return temp_dir


@pytest.fixture
def sample_z_raporu():
    """Ornek Z raporu metni (test icin)."""
    return """Z RAPORU
TARIH: 15/01/2025
SAAT: 18:30
BELGE NO: 001234
FIRMA ADI: TEST MARKET

BRUT: 15000,00
KDV: 2700,00
NET: 12300,00

NAKIT: 8000,00
KREDI KARTI: 4300,00
TOPLAM: 12300,00
"""


@pytest.fixture
def sample_parsed():
    """Ornek parse edilmis Z raporu verisi."""
    return {
        "tarih": "15/01/2025",
        "saat": "18:30",
        "z_no": "",
        "belge_no": "001234",
        "firma_adi": "TEST MARKET",
        "brut": 15000.0,
        "net_toplam": 12300.0,
        "kdv": 2700.0,
        "nakit": 8000.0,
        "kredi_karti": 4300.0,
        "yemek_ceki": 0.0,
        "iadeler": 0.0,
        "toplam_tahsilat": 12300.0,
        "urunler": [],
        "kdv_kalemleri": [],
    }


@pytest.fixture
def sample_mukellefler():
    """Ornek mükellef listesi."""
    return [
        {"adi": "AHMET YILMAZ", "kisa_adi": "AHMET", "vkn": "1234567890"},
        {"adi": "MEHMET DEMIR", "kisa_adi": "MEHMET", "vkn": "9876543210"},
        {"adi": "ZEYNEP KAYA", "kisa_adi": "ZEYNEP", "vkn": "5555555555"},
    ]


@pytest.fixture(autouse=True)
def _reset_ocr_cache():
    """Her test oncesi OCR cache'ini temizle."""
    yield
    try:
        from ocr_cache import ocr_cache_temizle
        ocr_cache_temizle()
    except Exception:
        pass
