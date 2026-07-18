import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

AUTH_FILE = os.path.join(DATA_DIR, "auth_config.json")
HESAP_FILE = os.path.join(DATA_DIR, "hesap_kodlari.json")
GECMIS_KLASORU = os.path.join(DATA_DIR, "gecmis")
MUKELLEF_FILE = os.path.join(DATA_DIR, "mukellefler.json")
FISLER_KLASORU = os.path.join(DATA_DIR, "fisler")
YEDEK_KLASORU = os.path.join(DATA_DIR, "yedekler")
URUN_KODLARI_FILE = os.path.join(DATA_DIR, "urun_kodlari.json")
SABLON_FILE = os.path.join(DATA_DIR, "luca_sablonu.xlsx")
EMAIL_FILE = os.path.join(DATA_DIR, "email_config.json")
NILVERA_FILE = os.path.join(DATA_DIR, "nilvera_config.json")
DUZELTME_SOZLUK = os.path.join(DATA_DIR, "duzeltme_sozlugu.json")
OGRENILEN_SOZLUK = os.path.join(DATA_DIR, "ogrenilen_sozluk.json")
OGRENILEN_ALANLAR = os.path.join(DATA_DIR, "ogrenilen_alanlar.json")

GOT_OCR_API = "got_ocr_api_url"

BILINEN_BANKALAR = [
    "İş Bankası", "İşbank", "ISBANK", " İş Bank",
    "is Bankas1", "İS BANKAS1", "İs Bankas1", "IS BANKASI",
    "Garanti", "GARANTİ", "Garanti BBVA",
    "Yapı Kredi", "YAPI KREDI", "Yapikredi",
    "Akbank", "AKBANK", "Ak Bank",
    "QNB Finansbank", "Finansbank", "FINANSBANK",
    "Halkbank", "HALKBANK", "Halk Bank",
    "Vakıfbank", "VAKIFBANK", "Vakif Bank",
    "Denizbank", "DENIZBANK", "Deniz Bank",
    "TEB", "TÜRKİYE EKONOMİ BANKASI", "Turkiye Ekonomi Bankasi",
    "Ziraat", "ZİRAAT", "T.C. ZİRAAT",
    "Ptt", "PTT", "PTT Posta",
    "Albaraka", "ALBARAKA",
    "Kuveyt Türk", "KUVEYT",
    "Türkiye Finans", "TURKIYE FINANS",
    "ING", "ING Bank",
    "HSBC", "HSBC Bank",
    "Anadolubank", "ANADOLUBANK",
]

BANKA_REGEX = [
    (r'[İIiı]\s*[Ss]\s+BANKA[sşSŞ1ıiI]', "İş Bankası"),
    (r'GARANT[İIi]', "Garanti"),
    (r'AK\s*BANK', "Akbank"),
    (r'YAPI\s*KREDI', "Yapı Kredi"),
    (r'HALK\s*BANK', "Halkbank"),
    (r'VAKIF\s*BANK', "Vakıfbank"),
    (r'DENIZ\s*BANK', "Denizbank"),
    (r'FINANS\s*BANK', "QNB Finansbank"),
    (r'QNB\s*BELO', "QNB Finansbank"),
    (r'Z[İI]RAAT', "Ziraat"),
    (r'HSBC', "HSBC"),
    (r'ING', "ING Bank"),
]

BASIT_USUL_KOLONLAR = [
    "İŞLEM", "KATEGORİ", "BELGE TÜRÜ", "BELGE TARİHİ", "FİŞ TARİHİ",
    "FİŞ NO", "BELGE NO", "MÜKELLEF/ALICI TC KİMLİK NO",
    "BAĞLI OLDUĞU VERGİ DAİRESİ", "MÜKELLEF/ALICI ÜNVAN",
    "MÜKELLEF/ALICI SOYADI", "ADRES", "PLAKA NO", "KİLOMETRE",
    "CİNSİ", "GİDER TÜRÜ", "KDV Oranları GİRİŞ",
    "KDV Oranları ÇIKIŞ", "STOK KODU", "MALZEME/HİZMET ADI",
    "MİKTAR", "BİRİM FİYAT", "TUTAR", "TUTAR (TL)",
    "KDV ORANI (%)", "İSKONTO ORANI (%)", "İSKONTO TUTARI (TL)",
    "VERGİLER DAHİL TOPLAM", "KDV TUTARI", "GENEL TOPLAM",
    "KREDİ KARTI İLE TAHSİLAT", "TAHSİL EDİLEN", "KALEM SAYISI",
    "SIRA NO", "ÖZEL KOD", "AÇIKLAMA",
]
