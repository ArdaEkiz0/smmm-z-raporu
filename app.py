import streamlit as st
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
import pandas as pd
import re
import io
import os
import math
import glob
import json
import shutil
import logging
from datetime import datetime, timedelta
from PIL import Image, ImageFilter, ImageOps


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("smmm")

st.set_page_config(page_title="SMMM Z Raporu Sistemi", layout="wide", page_icon=":ledger:")

st.components.v1.html("""
<script>
if (localStorage.getItem("smmm_auth") === "1" && window.location.search !== "?smmm_auth=1") {
    window.location.search = "?smmm_auth=1";
}
</script>
""", height=0)

AUTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_config.json")

def auth_ok():
    if "auth_ok" in st.session_state and st.session_state.auth_ok:
        return True
    if st.query_params.get("smmm_auth") == "1":
        st.session_state.auth_ok = True
        return True
    return False

if not auth_ok():
    pws = []
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                pws = json.load(f).get("passwords", [])
        except Exception:
            pass
    if pws:
        st.title("SMMM Z Raporu Sistemi")
        st.markdown("Yetkili kullanıcı girişi")
        pwd = st.text_input("Şifre", type="password", placeholder="Şifrenizi girin")
        if st.button("Giriş", type="primary"):
            if pwd in pws:
                st.session_state.auth_ok = True
                st.components.v1.html("""
                <script>
                try { localStorage.setItem("smmm_auth", "1"); } catch(e) {}
                window.location.search = "?smmm_auth=1";
                </script>
                """, height=0)
                st.rerun()
            else:
                st.error("Geçersiz şifre")
        st.stop()

if "mod" not in st.session_state:
    st.session_state.mod = "Bilanço"

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

HESAP_FILE = os.path.join(DATA_DIR, "hesap_kodlari.json")
GECMIS_KLASORU = os.path.join(DATA_DIR, "gecmis")
MUKELLEF_FILE = os.path.join(DATA_DIR, "mukellefler.json")
FISLER_KLASORU = os.path.join(DATA_DIR, "fisler")
YEDEK_KLASORU = os.path.join(DATA_DIR, "yedekler")
URUN_KODLARI_FILE = os.path.join(DATA_DIR, "urun_kodlari.json")
SABLON_FILE = os.path.join(DATA_DIR, "luca_sablonu.xlsx")

for klasor in [GECMIS_KLASORU, FISLER_KLASORU, YEDEK_KLASORU]:
    os.makedirs(klasor, exist_ok=True)

def otomatik_yedekle():
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        yedek_klasor = os.path.join(YEDEK_KLASORU, f"auto_{timestamp}")
        os.makedirs(yedek_klasor, exist_ok=True)
        for fp in [HESAP_FILE, MUKELLEF_FILE, URUN_KODLARI_FILE]:
            if os.path.exists(fp):
                shutil.copy2(fp, yedek_klasor)
        if os.path.exists(GECMIS_KLASORU):
            shutil.copytree(GECMIS_KLASORU, os.path.join(yedek_klasor, "gecmis"), dirs_exist_ok=True)
        otomatik_yedek_sayisi = len(glob.glob(os.path.join(YEDEK_KLASORU, "auto_*")))
        if otomatik_yedek_sayisi > 10:
            eski_yedekler = sorted(glob.glob(os.path.join(YEDEK_KLASORU, "auto_*")))
            for eski in eski_yedekler[:otomatik_yedek_sayisi - 10]:
                shutil.rmtree(eski, ignore_errors=True)
        log.info(f"Otomatik yedek oluşturuldu: {yedek_klasor}")
        return True
    except Exception as e:
        log.error(f"Otomatik yedek hatası: {e}")
        return False

def dosya_oku(filepath, varsayilan=None):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Dosya okunamadi {filepath}: {e}")
    return varsayilan if varsayilan is not None else {}

def dosya_yaz(filepath, veri):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Dosya yazilamadi {filepath}: {e}")
        raise

def gorsel_hazirla(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    w, h = img.size
    target_h = 3000
    if h < target_h:
        scale = target_h / h
        img = img.resize((int(w * scale), target_h), Image.LANCZOS)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = ImageOps.autocontrast(img, cutoff=2)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150))
    img = img.point(lambda x: 0 if x < 180 else 255)
    return img

@st.cache_resource
def load_ocr():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return pytesseract
    except Exception as e:
        log.warning(f"OCR (tesseract) yüklenemedi: {e}")
        return None

ocr_engine = load_ocr()

def ocr_image(img: Image.Image) -> str:
    if ocr_engine is None:
        return ""
    hazir = gorsel_hazirla(img)
    try:
        text = ocr_engine.image_to_string(hazir, lang="tur+eng", config="--psm 4 --oem 3")
        if not text.strip():
            text = ocr_engine.image_to_string(hazir, lang="tur+eng", config="--psm 6 --oem 3")
        return text.strip()
    except Exception:
        return ""

def parse_tutar(s):
    if not s:
        return 0.0
    s = s.strip().replace(" ", "")
    virgul = "," in s
    nokta = "." in s
    if virgul and nokta:
        s = s.replace(".", "").replace(",", ".")
    elif virgul:
        s = s.replace(",", ".")
    elif nokta:
        parts = s.split(".")
        if len(parts) > 1 and len(parts[-1]) <= 2:
            s = s.replace(",", "")
        else:
            s = s.replace(".", "")
    try:
        val = float(s)
        return val if val == val else 0.0
    except (ValueError, TypeError):
        return 0.0

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

def banka_bul(text):
    if not text:
        return None
    for banka in BILINEN_BANKALAR:
        if banka.lower() in text.lower():
            return banka
    for pat, adi in BANKA_REGEX:
        if re.search(pat, text, re.IGNORECASE):
            return adi
    return None

def salon_bul(text):
    if not text:
        return None
    satirlar = text.split("\n")
    for i, satir in enumerate(satirlar[:10]):
        s = satir.strip()
        if not s or len(s) < 3:
            continue
        if any(x in s.lower() for x in ["vd", "tc:", "tel", "vergi", "sirket", "mağaza", "magaza"]):
            continue
        if re.search(r'\d{2}[./-]\d{2}[./-]\d{4}', s):
            continue
        if any(x in s.lower() for x in ["rapor", "z raporu", "gunluk", "günlük", "fiş no", "fis no", "saat"]):
            continue
        if len(s) > 5 and not re.match(r'^[\d\s*.,]+$', s):
            return s
    return None

def parse_z_raporu(text):
    sonuc = {
        "tarih": None, "belge_no": None, "z_no": None,
        "nakit": 0, "kredi_karti": 0, "yemek_ceki": 0,
        "toplam_tahsilat": 0, "iadeler": 0, "net_toplam": 0,
        "kdv_kalemleri": [], "brut": 0, "urunler": [], "ham_text": text,
        "banka_adi": None, "firma_adi": None,
    }

    if not text or not text.strip():
        return sonuc

    t = text
    t_duz = " ".join(text.split())

    sonuc["firma_adi"] = salon_bul(t)
    sonuc["banka_adi"] = banka_bul(t_duz)

    tarih_match = re.search(r'(\d{2})[./-](\d{2})[./-](\d{4})', t_duz)
    if tarih_match:
        sonuc["tarih"] = f"{tarih_match.group(1)}.{tarih_match.group(2)}.{tarih_match.group(3)}"

    z_no = re.search(r'Z\s*No[:\s]*(\d+)', t_duz, re.IGNORECASE)
    if z_no:
        sonuc["z_no"] = z_no.group(1)
    fis_no = re.search(r'Fi[sş]\s*No[:\s]*(\d+)', t_duz, re.IGNORECASE)
    if fis_no:
        sonuc["belge_no"] = fis_no.group(1)
    elif z_no:
        sonuc["belge_no"] = z_no.group(1)

    m = re.search(r'Br[uü]t\s+\*?\s*([\d.,]+)', t_duz, re.IGNORECASE)
    if m:
        val = parse_tutar(m.group(1))
        if val > 0:
            sonuc["brut"] = val

    net_patterns = [
        r'Net\s+C[iı]ro\s+\*?\s*([\d.,]+)',
        r'NET\s+CIRO\s+\*?\s*([\d.,]+)',
        r'NE[TI]\s+SATI[SŞ]\s+\*?\s*([\d.,]+)',
        r'NE[TI]\s+C[Iı][Rr][Oo]\s+\*?\s*([\d.,]+)',
        r'NET\s+SATI[SŞ]\s+\*?\s*([\d.,]+)',
        r'Net\s+\*?\s*([\d.,]+)',
    ]
    for pat in net_patterns:
        net = re.search(pat, t_duz, re.IGNORECASE)
        if net:
            val = parse_tutar(net.group(1))
            if val > 0:
                sonuc["net_toplam"] = val
                break

    iade_patterns = [
        r'Fi?s\s+[Ff]?[İiI]ptal\s+\d+\s*\*?\s*([\d.,]+)',
        r'(?:FPTAL|IPTAL|fptal|iptal)\s+\d+\s*\*?\s*([\d.,]+)',
        r'FIS\s+IPTAL\s+\d+\s*\*?\s*([\d.,]+)',
        r'FIS\s+İPTAL\s+\d+\s*\*?\s*([\d.,]+)',
        r'Fiş\s+İptal\s+\d+\s*\*?\s*([\d.,]+)',
        r'FIS\s+IPTAL\s*\*?\s*([\d.,]+)',
        r'FIS\s+İPTAL\s*\*?\s*([\d.,]+)',
        r'Fiş\s+İptal\s*\*?\s*([\d.,]+)',
    ]
    for pat in iade_patterns:
        iade = re.search(pat, t_duz, re.IGNORECASE)
        if iade:
            val = parse_tutar(iade.group(1))
            if val > 0:
                sonuc["iadeler"] = val
                break

    nakit_patterns = [
        r'NAK[İiI]T\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
        r'NAKIT\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
        r'[Nn]akit\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
        r'NAK[İiI]T\s+\*?\+?\s*([\d.,]+)',
        r'NAKIT\s+\*?\+?\s*([\d.,]+)',
    ]
    for pat in nakit_patterns:
        nakit = re.search(pat, t_duz, re.IGNORECASE)
        if nakit:
            groups = nakit.groups()
            if len(groups) >= 2:
                sonuc["nakit"] = parse_tutar(groups[1])
            else:
                sonuc["nakit"] = parse_tutar(groups[0])
            if sonuc["nakit"] > 0:
                break

    kart_patterns = [
        r'[Kk]\.?\s*[Kk]art[iıI]\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
        r'KRED[IiİI]\s*KART[IiİI]\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
        r'KREDI\s*KARTI\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
        r'[Kk]\.?\s*[Kk]art[iıI]\s+\*?\+?\s*([\d.,]+)',
        r'KRED[IiİI]\s*KART[IiİI]\s+\*?\+?\s*([\d.,]+)',
        r'KREDI\s*KARTI\s+\*?\+?\s*([\d.,]+)',
    ]
    for pat in kart_patterns:
        kart = re.search(pat, t_duz, re.IGNORECASE)
        if kart:
            groups = kart.groups()
            if len(groups) >= 2:
                sonuc["kredi_karti"] = parse_tutar(groups[1])
            else:
                sonuc["kredi_karti"] = parse_tutar(groups[0])
            if sonuc["kredi_karti"] > 0:
                break

    yemek_patterns = [
        r'YEMEK\s+CEK[IiİI]\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
        r'[Yy]emek\s*[Cc]eki[/]?[Kk]art[iı]\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
        r'[Yy]emek\s*[Cc]eki[/]?[Kk]art[iı]\s+\*?\+?\s*([\d.,]+)',
        r'YEMEK\s*[Cc]EK[IiİI]\s+\*?\+?\s*([\d.,]+)',
        r'Yemek\s+Ceki\s+\*?\+?\s*([\d.,]+)',
    ]
    for pat in yemek_patterns:
        yemek = re.search(pat, t_duz, re.IGNORECASE)
        if yemek:
            groups = yemek.groups()
            if len(groups) >= 2:
                sonuc["yemek_ceki"] = parse_tutar(groups[1])
            else:
                sonuc["yemek_ceki"] = parse_tutar(groups[0])
            if sonuc["yemek_ceki"] > 0:
                break

    toplam_tahsilat = sonuc["nakit"] + sonuc["kredi_karti"] + sonuc["yemek_ceki"]
    if toplam_tahsilat > 0:
        sonuc["toplam_tahsilat"] = toplam_tahsilat

    URUN_CHARS = r'[A-Za-z\u011e\u011f\u015e\u015f\u0130\u0131\u00d6\u00f6\u00dc\u00fc\u00c7\u00e7& ]'
    yanlis_kelimeler = ["TOPLAM", "KDV", "TOPKDV", "MALI", "SATIS", "KUM", "KUM",
                        "VERGI", "ODEME", "FIS", "SLIP", "FPTAL", "IPTAL",
                        "SAYI", "EKU", "MUSTERI", "RAPOR", "TURLERI",
                        "CIRO", "GENEL", "TARIH", "SAAT", "NO:", "NAKIT",
                        "BANKA", "ADET"]

    urun_pattern1 = re.finditer(
        rf'({URUN_CHARS}{{2,}}?)\s*%(\d+)\s+(\d+)\s*\*?\s*([\d.,]+)',
        t_duz, re.IGNORECASE
    )
    for um in urun_pattern1:
        urun_adi = um.group(1).strip()
        if any(yk in urun_adi.upper() for yk in yanlis_kelimeler):
            continue
        oran = int(um.group(2))
        miktar = parse_tutar(um.group(3))
        tutar = parse_tutar(um.group(4))
        if tutar > 0 or miktar > 0:
            sonuc["urunler"].append({"urun": urun_adi, "oran": oran, "miktar": miktar, "tutar": tutar})

    mevcut_urunler = {u["urun"].upper() for u in sonuc["urunler"]}
    urun_pattern2 = re.finditer(
        rf'({URUN_CHARS}{{2,}}?)\s+(\d+)\s*%(\d+)\s*\*?\s*([\d.,]+)',
        t_duz, re.IGNORECASE
    )
    for um in urun_pattern2:
        urun_adi = um.group(1).strip()
        if urun_adi.upper() in mevcut_urunler:
            continue
        if any(yk in urun_adi.upper() for yk in yanlis_kelimeler):
            continue
        oran = int(um.group(3))
        miktar = parse_tutar(um.group(2))
        tutar = parse_tutar(um.group(4))
        if tutar > 0 or miktar > 0:
            sonuc["urunler"].append({"urun": urun_adi, "oran": oran, "miktar": miktar, "tutar": tutar})
            mevcut_urunler.add(urun_adi.upper())

    urun_pattern3 = re.finditer(
        rf'({URUN_CHARS}{{2,}}?)\s*%(\d+)\s*(?:Mktr|ADT|miktar)?\s*\*?\s*([\d.,]+)\s*\*?\s*([\d.,]+)',
        t_duz, re.IGNORECASE
    )
    for um in urun_pattern3:
        urun_adi = um.group(1).strip()
        if urun_adi.upper() in mevcut_urunler:
            continue
        if any(yk in urun_adi.upper() for yk in yanlis_kelimeler):
            continue
        oran = int(um.group(2))
        miktar = parse_tutar(um.group(3))
        tutar = parse_tutar(um.group(4))
        if tutar > 0 or miktar > 0:
            sonuc["urunler"].append({"urun": urun_adi, "oran": oran, "miktar": miktar, "tutar": tutar})
            mevcut_urunler.add(urun_adi.upper())

    urun_pattern4 = re.finditer(
        rf'({URUN_CHARS}{{2,}}?)\s*%(\d+)\s*\*?\s*([\d.,]+)',
        t_duz, re.IGNORECASE
    )
    for um in urun_pattern4:
        urun_adi = um.group(1).strip()
        if urun_adi.upper() in mevcut_urunler:
            continue
        if any(yk in urun_adi.upper() for yk in yanlis_kelimeler):
            continue
        oran = int(um.group(2))
        tutar = parse_tutar(um.group(3))
        if tutar > 10:
            sonuc["urunler"].append({"urun": urun_adi, "oran": oran, "miktar": 0, "tutar": tutar})

    kdv_data = {}

    vergi_patterns = [
        r'\*?\s*([\d.,]+)\s*%(\d+)\s*TOPLAM\s*\*?\s*([\d.,]+)\s*TOPKDV',
        r'%(\d+)\s*TOPLAM\s*\*?\s*([\d.,]+)\s*.*?TOPKDV\s*\*?\s*([\d.,]+)',
        r'%(\d+)\s*TOPLAM\s*\*?\s*([\d.,]+)\s*.*?KDV\s*\*?\s*([\d.,]+)',
        r'TOPLAM\s*%(\d+)\s*\*?\s*([\d.,]+)\s*TOPKDV\s*%?\*?\s*([\d.,]+)',
        r'TOPLAM\s*%(\d+)\s*\*?\s*([\d.,]+)\s*KDV\s*%?\*?\s*([\d.,]+)',
    ]
    for pat in vergi_patterns:
        for vm in re.finditer(pat, t_duz, re.IGNORECASE):
            groups = vm.groups()
            if pat.startswith(r'\*?\s*([\d.,]+)\s*%'):
                brut_v = parse_tutar(groups[0])
                oran = int(groups[1])
                kdv_v = parse_tutar(groups[2])
            else:
                oran = int(groups[0])
                brut_v = parse_tutar(groups[1])
                kdv_v = parse_tutar(groups[2])
            if oran > 0 and (brut_v > 0 or kdv_v > 0):
                if brut_v > kdv_v:
                    matrah_v = round(brut_v - kdv_v, 2)
                else:
                    matrah_v = brut_v
                if oran not in kdv_data:
                    kdv_data[oran] = {"oran": oran, "matrah": matrah_v, "kdv_tutari": kdv_v}

    if not kdv_data:
        kdv_bireysel = re.finditer(r'%(\d+)\s*\*?\s*([\d.,]+)\s*KDV\s*\*?\s*([\d.,]+)', t_duz, re.IGNORECASE)
        for km in kdv_bireysel:
            oran = int(km.group(1))
            matrah_v = parse_tutar(km.group(2))
            kdv_v = parse_tutar(km.group(3))
            if oran > 0 and matrah_v > 0:
                kdv_data[oran] = {"oran": oran, "matrah": matrah_v, "kdv_tutari": kdv_v}

    for u in sonuc["urunler"]:
        oran = u["oran"]
        tutar = u["tutar"]
        if tutar <= 0 or oran == 0:
            continue
        if oran not in kdv_data:
            net_tutar = round(tutar / (1 + oran / 100), 2)
            kdv_tutar = round(tutar - net_tutar, 2)
            kdv_data[oran] = {"oran": oran, "matrah": net_tutar, "kdv_tutari": kdv_tutar}

    sonuc["kdv_kalemleri"] = sorted(kdv_data.values(), key=lambda x: x["oran"])

    if sonuc["brut"] == 0 and sonuc["net_toplam"] > 0:
        sonuc["brut"] = sonuc["net_toplam"]
    if sonuc["net_toplam"] == 0 and sonuc["brut"] > 0:
        sonuc["net_toplam"] = sonuc["brut"]
    if sonuc["brut"] == 0 and sonuc["urunler"]:
        sonuc["brut"] = round(sum(u["tutar"] for u in sonuc["urunler"]), 2)
    if sonuc["brut"] == 0 and kdv_data:
        sonuc["brut"] = round(sum(k["matrah"] + k["kdv_tutari"] for k in kdv_data.values()), 2)
    if sonuc["brut"] == 0 and sonuc["toplam_tahsilat"] > 0:
        sonuc["brut"] = sonuc["toplam_tahsilat"]
    if sonuc["net_toplam"] == 0:
        sonuc["net_toplam"] = sonuc["brut"]

    if sonuc["toplam_tahsilat"] == 0:
        sonuc["toplam_tahsilat"] = sonuc["brut"]

    return sonuc

def varsayilan_kodlar():
    return {
        "kredi_karti": "108.01", "nakit": "100.01", "yemek_ceki": "108.03",
        "satis_1": "600.01", "satis_10": "600.05",
        "satis_20": "600.04",
        "kdv_1": "391.01", "kdv_10": "391.05",
        "kdv_20": "391.04", "iadeler": "610.01",
    }

def urun_kodlari_varsayilan():
    return [
        {"pattern": "EKMEK", "hesap_kodu": "600.06", "aciklama": "Ekmek Satışı"},
        {"pattern": "SİGARA", "hesap_kodu": "600.07", "aciklama": "Sigara Satışı"},
        {"pattern": "SIGARA", "hesap_kodu": "600.07", "aciklama": "Sigara Satışı"},
    ]

def urun_kodlari_yukle():
    return dosya_oku(URUN_KODLARI_FILE, urun_kodlari_varsayilan())

def urun_kodlari_kaydet(kodlar):
    dosya_yaz(URUN_KODLARI_FILE, kodlar)

def urun_kodu_bul(urun_adi, urun_kodlari):
    if not urun_adi or not urun_kodlari:
        return None
    ua = urun_adi.upper()
    for k in urun_kodlari:
        if k["pattern"].upper() in ua:
            return k
    return None

def data_to_luca_rows(data, hesap_kodlari, fis_no_start=1, urun_kodlari=None):
    rows = []
    fis_no = fis_no_start
    tarih = data.get("tarih", datetime.now().strftime("%d.%m.%Y"))
    z_no = data.get("z_no") or data.get("belge_no") or str(fis_no)
    banka = data.get("banka_adi", "")
    firma = data.get("firma_adi", "")
    aciklama = f"{z_no} nolu Z Raporu"
    if banka:
        aciklama += f" - {banka}"
    if firma:
        aciklama += f" ({firma})"
    evrak_no = z_no
    musteri = data.get("mukellef_adi", "")

    def satir(hesap, detay, borc, alacak):
        return {"Fiş No": fis_no, "Fiş Tarihi": tarih, "Fiş Açıklama": aciklama,
                "Hesap Kodu": hesap, "Evrak No": evrak_no, "Evrak Tarihi": tarih,
                "Detay Açıklama": detay, "Borç": borc, "Alacak": alacak,
                "Miktar": None, "Belge Türü": "Z Raporu", "Para Birimi": None,
                "Kur": None, "Döviz Tutar": None}

    iade = data.get("iadeler", 0) or 0
    kart = data["kredi_karti"]
    nakit = data["nakit"]
    yemek = data["yemek_ceki"]

    if iade > 0:
        kalan = iade
        if kart > 0:
            dus = min(kart, kalan)
            kart = round(kart - dus, 2)
            kalan = round(kalan - dus, 2)
        if kalan > 0 and nakit > 0:
            dus = min(nakit, kalan)
            nakit = round(nakit - dus, 2)
            kalan = round(kalan - dus, 2)
        if kalan > 0 and yemek > 0:
            dus = min(yemek, kalan)
            yemek = round(yemek - dus, 2)

    if kart > 0:
        kart_detay = f"Kredi Kartı Tahsilatı - {musteri}"
        if banka:
            kart_detay = f"{banka} KK Tahsilatı - {musteri}"
        rows.append(satir(hesap_kodlari.get("kredi_karti", "108.01"), kart_detay, kart, 0))
    if nakit > 0:
        rows.append(satir(hesap_kodlari.get("nakit", "100.01"), f"Nakit Tahsilat - {musteri}", nakit, 0))
    if yemek > 0:
        rows.append(satir(hesap_kodlari.get("yemek_ceki", "108.03"), f"Yemek Çeki/Kartı - {musteri}", yemek, 0))

    if data["kredi_karti"] == 0 and data["nakit"] == 0 and data["yemek_ceki"] == 0:
        toplam = data["toplam_tahsilat"] or data["net_toplam"] or data["brut"]
        if toplam > 0:
            rows.append(satir(hesap_kodlari.get("kredi_karti", "108.01"), f"Tahsilat - {musteri}", toplam, 0))

    kdv_oran_hesap = {1: "391.01", 10: "391.05", 20: "391.04"}
    satis_oran_hesap = {1: "600.01", 10: "600.05", 20: "600.04"}

    urun_kodlari = urun_kodlari or []
    urun_bazli = {}
    genel_kdv = {}

    for urun in data.get("urunler", []):
        ua = urun.get("urun", "")
        oran = urun.get("oran", 0)
        tutar = urun.get("tutar", 0)
        if tutar <= 0 or oran == 0:
            continue
        eslesme = urun_kodu_bul(ua, urun_kodlari)
        net_tutar = round(tutar / (1 + oran / 100), 2)
        kdv_tutar = round(tutar - net_tutar, 2)
        if eslesme:
            kod = eslesme["hesap_kodu"]
            if kod not in urun_bazli:
                urun_bazli[kod] = {"matrah": 0, "kdv": 0, "aciklama": eslesme["aciklama"], "oran": oran}
            urun_bazli[kod]["matrah"] += net_tutar
            urun_bazli[kod]["kdv"] += kdv_tutar
        else:
            if oran not in genel_kdv:
                genel_kdv[oran] = {"matrah": 0, "kdv": 0}
            genel_kdv[oran]["matrah"] += net_tutar
            genel_kdv[oran]["kdv"] += kdv_tutar

    for kod, vb in urun_bazli.items():
        rows.append(satir(kod, vb["aciklama"], 0, round(vb["matrah"], 2)))
        if vb["kdv"] > 0.005:
            kdv_kod = hesap_kodlari.get(f"kdv_{vb['oran']}", kdv_oran_hesap.get(vb['oran'], f"391.{vb['oran']:02d}"))
            rows.append(satir(kdv_kod, f"%{vb['oran']} Hesaplanan KDV", 0, round(vb["kdv"], 2)))

    for oran in sorted(genel_kdv.keys()):
        gk = genel_kdv[oran]
        if gk["matrah"] > 0.005:
            kod = hesap_kodlari.get(f"satis_{oran}", satis_oran_hesap.get(oran, f"600.{oran:02d}"))
            rows.append(satir(kod, f"%{oran} KDV'li Satış", 0, round(gk["matrah"], 2)))
        if gk["kdv"] > 0.005:
            kdv_kod = hesap_kodlari.get(f"kdv_{oran}", kdv_oran_hesap.get(oran, f"391.{oran:02d}"))
            rows.append(satir(kdv_kod, f"%{oran} Hesaplanan KDV", 0, round(gk["kdv"], 2)))

    kdv_toplam = sum((kv.get("matrah", 0) or 0) + (kv.get("kdv_tutari", 0) or 0) for kv in data["kdv_kalemleri"])
    kdv_guvenilir = kdv_toplam <= data.get("brut", 0) * 1.1 or not data["urunler"]

    for kdv in data["kdv_kalemleri"] if kdv_guvenilir else []:
        oran = kdv["oran"]
        kalan_matrah = kdv["matrah"]
        kalan_kdv = kdv["kdv_tutari"]
        if oran in genel_kdv:
            kalan_matrah -= genel_kdv[oran]["matrah"]
            kalan_kdv -= genel_kdv[oran]["kdv"]
        vb_toplam_matrah = sum(v["matrah"] for v in urun_bazli.values() if v["oran"] == oran)
        kalan_matrah -= vb_toplam_matrah
        vb_toplam_kdv = sum(v["kdv"] for v in urun_bazli.values() if v["oran"] == oran)
        kalan_kdv -= vb_toplam_kdv
        if kalan_matrah < -0.005 or kalan_kdv < -0.005:
            kalan_matrah = 0; kalan_kdv = 0
        if kalan_matrah > 0.005:
            kod = hesap_kodlari.get(f"satis_{oran}", satis_oran_hesap.get(oran, f"600.{oran:02d}"))
            rows.append(satir(kod, f"%{oran} KDV'li Satış", 0, round(kalan_matrah, 2)))
        if kalan_kdv > 0.005:
            kdv_kod = hesap_kodlari.get(f"kdv_{oran}", kdv_oran_hesap.get(oran, f"391.{oran:02d}"))
            rows.append(satir(kdv_kod, f"%{oran} Hesaplanan KDV", 0, round(kalan_kdv, 2)))

    if len(data["urunler"]) == 0 and len(data["kdv_kalemleri"]) == 0:
        net = data["net_toplam"] or data["toplam_tahsilat"] or data["brut"]
        if net > 0:
            rows.append(satir(hesap_kodlari.get("satis_20", "600.04"), f"Satış - {musteri}", 0, net))

    if data["iadeler"] > 0:
        rows.append(satir(hesap_kodlari.get("iadeler", "610.01"), f"Fiş İptal - {musteri}", data["iadeler"], 0))

    return rows

@st.cache_data
def hesapla_luca_rows(results, hesap_kodlari, urun_kodlari):
    all_luca_rows = []
    fc = 1
    for r in results:
        if "error" in r:
            continue
        rows = data_to_luca_rows(r, hesap_kodlari, fc, urun_kodlari)
        all_luca_rows.extend(rows)
        fc += 1
    return all_luca_rows

@st.cache_data
def generate_excel_cached(all_luca_rows_tuple):
    return generate_excel(list(all_luca_rows_tuple))

def generate_excel(all_rows):
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Luca Aktarım"
    headers = ["Fiş No", "Fiş Tarihi", "Fiş Açıklama", "Hesap Kodu", "Evrak No", "Evrak Tarihi",
               "Detay Açıklama", "Borç", "Alacak", "Miktar", "Belge Türü", "Para Birimi", "Kur", "Döviz Tutar"]
    hfont = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    halign = Alignment(horizontal="center", vertical="center", wrap_text=True)
    border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = hfont
        cell.fill = hfill
        cell.alignment = halign
        cell.border = border
    for row_idx, row_data in enumerate(all_rows, 2):
        for col_idx, header in enumerate(headers, 1):
            val = row_data.get(header, "")
            if val is None:
                val = ""
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = border
            if col_idx in (8, 9):
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal="right")
    widths = [8, 14, 40, 12, 12, 14, 30, 14, 14, 10, 14, 12, 10, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w
    wb.save(output)
    return output.getvalue()

BASIT_USUL_KOLONLAR = [
    "İŞLEM", "KATEGORİ", "BELGE TURU", "EVRAK TARİHİ", "KAYIT TARİHİ", "SERİ NO",
    "EVRAK NO", "TCKN/VKN", "VERGİ DAİRESİ", "SOYADI ÜNVAN", "ADI DEVAMI", "ADRES",
    "CARİ HESAP", "KDV İSTİSNASI", "KOD", "BELGE TÜRÜ(DB)", "ALIŞ/SATIŞ TÜRÜ",
    "KAYIT ALT TÜRÜ", "MAL VE HİZMET KODU", "AÇIKLAMA", "MİKTAR",
    "B.FİYAT", "TUTAR", "TEVKİFAT", "KDV ORANI", "ÖZEL MATRAH İŞLEM BEDELİ",
    "MATRAHTAN DÜŞÜLECEK TUTAR", "MATRAHA DAHİL OLMAYAN BEDEL",
    "KDV TUTARI", "TOPLAM TUTAR", "KREDİLİ TUTAR", "STOPAJ KODU", "STOPAJ TUTARI",
    "DÖNEMSELLİK İLKESİ", "FAALİYET KODU", "ÖDEME TÜRÜ",
]

def generate_basit_usul_excel(results, mukellef_bilgi, sablon_data=None):
    output = io.BytesIO()
    border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))

    if sablon_data:
        wb = openpyxl.load_workbook(io.BytesIO(sablon_data))
        ws = wb.active
        kolonlar = [ws.cell(1, col).value or "" for col in range(1, ws.max_column + 1)]
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Serbest Meslek"
        kolonlar = BASIT_USUL_KOLONLAR
        hfont = Font(bold=True, color="FFFFFF", size=10)
        hfill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        halign = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for col_idx, header in enumerate(kolonlar, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = hfont
            cell.fill = hfill
            cell.alignment = halign
            cell.border = border

    evrak_tarihi = ""
    kayit_tarihi = ""
    evrak_no = ""
    tckn = (mukellef_bilgi or {}).get("vergi_no", "")
    vd = (mukellef_bilgi or {}).get("vd", "")
    unvan = (mukellef_bilgi or {}).get("adi", "")
    adres = (mukellef_bilgi or {}).get("notlar", "")

    def yaz_satir(satir):
        nonlocal row_idx
        for col_idx, header in enumerate(kolonlar, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=satir.get(header, ""))
            cell.border = border
        row_idx += 1

    row_idx = 2
    for r in results:
        if "error" in r:
            continue
        evrak_tarihi = r.get("tarih", "")
        kayit_tarihi = r.get("tarih", "")
        evrak_no = r.get("z_no", "") or r.get("belge_no", "")
        kk_tutar = r.get("kredi_karti", 0) or 0
        nakit_tutar = r.get("nakit", 0) or 0
        toplam_tahsilat = r.get("toplam_tahsilat", 0) or (kk_tutar + nakit_tutar) or 1

        def base_row():
            s = {}
            for k in kolonlar:
                s[k] = ""
            if len(kolonlar) >= 1:
                s[kolonlar[0]] = "1"
            if len(kolonlar) >= 2:
                s[kolonlar[1]] = "Defter Fişleri"
            if len(kolonlar) >= 3:
                s[kolonlar[2]] = "Z Raporu"
            for pos, val in [(3, evrak_tarihi), (4, kayit_tarihi),
                             (6, evrak_no), (7, tckn), (8, vd), (9, unvan), (11, adres)]:
                if len(kolonlar) > pos:
                    s[kolonlar[pos]] = val
            return s

        def kk_orani(brut):
            return round(brut * kk_tutar / toplam_tahsilat, 2) if toplam_tahsilat > 0 else 0

        urunler = r.get("urunler", [])
        kdv_kalemleri = r.get("kdv_kalemleri", [])

        if not urunler and not kdv_kalemleri:
            s = base_row()
            for k in kolonlar:
                if "ACIKLAMA" in k or "AÇIKLAMA" in k:
                    s[k] = f"Z Raporu {evrak_no}"
                    break
            brut = r.get("brut", 0) or toplam_tahsilat or 0
            for k in kolonlar:
                if k == "TUTAR":
                    s[k] = brut
                if "TOPLAM" in k and "TUTAR" in k:
                    s[k] = brut
                if "KREDILI" in k or "KREDİLİ" in k:
                    s[k] = kk_orani(brut)
            yaz_satir(s)
            continue

        if not urunler and kdv_kalemleri:
            for kv in kdv_kalemleri:
                s = base_row()
                for k in kolonlar:
                    if "ACIKLAMA" in k or "AÇIKLAMA" in k:
                        s[k] = f"Z Raporu {evrak_no} %{kv['oran']} KDV"
                    if "MIKTAR" in k or "MİKTAR" in k:
                        s[k] = ""
                    if k == "B.FİYAT" or k == "B.FIYAT":
                        s[k] = ""
                    if k == "TUTAR":
                        s[k] = kv.get("matrah", 0)
                    if k == "KDV ORANI" or k == "KDV ORAN":
                        s[k] = kv.get("oran", 0)
                    if "KDV TUTARI" in k or "KDV TUTAR" in k:
                        s[k] = kv.get("kdv_tutari", 0)
                    if "TOPLAM TUTAR" in k or "TOPLAM TUTAR" in k:
                        toplam_t = (kv.get("matrah", 0) or 0) + (kv.get("kdv_tutari", 0) or 0)
                        s[k] = toplam_t
                    if "KREDILI" in k or "KREDİLİ" in k:
                        toplam_t = (kv.get("matrah", 0) or 0) + (kv.get("kdv_tutari", 0) or 0)
                        s[k] = kk_orani(toplam_t)
                yaz_satir(s)
            continue

        for urun in urunler:
            s = base_row()
            ua = urun.get("urun", "")
            miktar = urun.get("miktar", 0) or 0
            brut_tutar = urun.get("tutar", 0) or 0
            oran = urun.get("oran", 0) or 0
            kdv_t = round(brut_tutar - (brut_tutar / (1 + oran / 100)), 2) if oran > 0 else 0

            for k in kolonlar:
                if "ACIKLAMA" in k or "AÇIKLAMA" in k:
                    s[k] = ua
                if "MIKTAR" in k or "MİKTAR" in k:
                    s[k] = miktar
                if k == "B.FİYAT" or k == "B.FIYAT":
                    s[k] = round(brut_tutar / miktar, 2) if miktar > 0 else ""
                if k == "TUTAR":
                    s[k] = round(brut_tutar / (1 + oran / 100), 2) if oran > 0 else brut_tutar
                if k == "KDV ORANI" or k == "KDV ORAN":
                    s[k] = oran
                if "KDV TUTARI" in k or "KDV TUTAR" in k:
                    s[k] = kdv_t
                if "TOPLAM TUTAR" in k or "TOPLAM TUTAR" in k:
                    s[k] = brut_tutar
                if "KREDILI" in k or "KREDİLİ" in k:
                    s[k] = kk_orani(brut_tutar)
            yaz_satir(s)

    for i, w in enumerate([10, 12, 14, 14, 14, 12, 14, 16, 16, 30, 20, 14, 16, 12, 14, 14, 14, 12, 16, 30, 10, 12, 14, 10, 10, 14, 16, 16, 14, 14, 14, 12, 12, 14, 14, 14, 14], 1):
        col_letter = chr(64 + i) if i <= 26 else chr(64 + (i - 1) // 26) + chr(65 + (i - 1) % 26)
        ws.column_dimensions[col_letter].width = w

    wb.save(output)
    return output.getvalue()

def mukellefler():
    return dosya_oku(MUKELLEF_FILE, [])

def gecmis_kaydet(results, hesap_kodlari, mukellef_adi=""):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    kayit = {
        "tarih": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "dosya_sayisi": len(results),
        "mukellef": mukellef_adi,
        "hesap_kodlari": hesap_kodlari,
        "sonuclar": []
    }
    for r in results:
        entry = {k: v for k, v in r.items() if k not in ("ocr_text", "ham_text")}
        entry["filename"] = r.get("filename", "")
        kayit["sonuclar"].append(entry)
    filepath = os.path.join(GECMIS_KLASORU, f"kayit_{timestamp}.json")
    dosya_yaz(filepath, kayit)
    return filepath

def gecmis_listele():
    kayitlar = []
    for fp in sorted(glob.glob(os.path.join(GECMIS_KLASORU, "*.json")), reverse=True):
        try:
            kayit = dosya_oku(fp)
            if kayit:
                kayit["dosya_yolu"] = fp
                kayitlar.append(kayit)
        except Exception as e:
            log.warning(f"Gecmis okunamadi {fp}: {e}")
    return kayitlar

def tum_fisleri_yukle():
    tum_fisler = []
    for fp in sorted(glob.glob(os.path.join(GECMIS_KLASORU, "*.json"))):
        try:
            kayit = dosya_oku(fp)
            for s in kayit.get("sonuclar", []):
                s["kayit_tarihi"] = kayit.get("tarih", "")
                s["mukellef"] = kayit.get("mukellef", "")
                tum_fisler.append(s)
        except Exception as e:
            log.warning(f"Fis yuklenemedi {fp}: {e}")
    return tum_fisler

def fis_sil(kayit_yolu, fis_index):
    try:
        kayit = dosya_oku(kayit_yolu)
        if not kayit or "sonuclar" not in kayit:
            return False
        if 0 <= fis_index < len(kayit["sonuclar"]):
            kayit["sonuclar"].pop(fis_index)
            kayit["dosya_sayisi"] = len(kayit["sonuclar"])
            if len(kayit["sonuclar"]) == 0:
                os.remove(kayit_yolu)
            else:
                dosya_yaz(kayit_yolu, kayit)
            return True
    except Exception as e:
        log.error(f"Fis silinemedi: {e}")
    return False

st.title("SMMM Z Raporu ve Fiş Yönetim Sistemi")

with st.sidebar:
    st.header("Aygıtlar")
    sayfa = st.radio("Sayfa Seç", ["Dashboard", "Z Raporu Yükle", "Fiş Geçmişi", "Mükellef Yönetimi", "KDV Özeti", "Ayarlar"], label_visibility="collapsed")

    st.divider()
    st.header("Mod")
    st.session_state.mod = st.radio("Muhasebe Türü", ["Bilanço", "Serbest Meslek"], index=0 if st.session_state.get("mod", "Bilanço") == "Bilanço" else 1, label_visibility="collapsed")

    if st.session_state.get("mod") == "Serbest Meslek":
        with st.expander("LUCA Şablonu", expanded=False):
            st.caption("LUCA'dan indirdiğiniz Excel şablonunu yükleyin (bir kez yeter)")
            yuklenen = st.file_uploader("Şablon Seç", type=["xlsx"], label_visibility="collapsed", key="luca_sablon_uploader")
            if yuklenen:
                data = yuklenen.read()
                with open(SABLON_FILE, "wb") as f:
                    f.write(data)
                st.session_state["luca_sabloni"] = data
                st.toast("Şablon kaydedildi!", icon="✅")
            if st.button("Şablonu Kaldır"):
                if os.path.exists(SABLON_FILE):
                    os.remove(SABLON_FILE)
                if "luca_sabloni" in st.session_state:
                    del st.session_state["luca_sabloni"]
                st.rerun()
            if os.path.exists(SABLON_FILE) and "luca_sabloni" not in st.session_state:
                with open(SABLON_FILE, "rb") as f:
                    st.session_state["luca_sabloni"] = f.read()
            if st.session_state.get("luca_sabloni"):
                st.success("✅ Şablon yüklü")

    st.divider()
    st.header("Hesap Kodları")
    if "hesap_kodlari" not in st.session_state:
        st.session_state.hesap_kodlari = dosya_oku(HESAP_FILE, varsayilan_kodlar())

    kod_etiketleri = [
        ("kredi_karti", "Banka (KK)"), ("nakit", "Banka (Nakit)"), ("yemek_ceki", "Yemek Çeki"),
        ("satis_1", "Satış %1"), ("satis_10", "Satış %10"),
        ("satis_20", "Satış %20"),
        ("kdv_1", "KDV %1"), ("kdv_10", "KDV %10"),
        ("kdv_20", "KDV %20"),
        ("iadeler", "Fiş İptal"),
    ]
    hesap_kodlari = {}
    for key, label in kod_etiketleri:
        hesap_kodlari[key] = st.text_input(label, value=st.session_state.hesap_kodlari.get(key, ""), key=f"hk_{key}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Kaydet", width="stretch"):
            dosya_yaz(HESAP_FILE, hesap_kodlari)
            st.session_state.hesap_kodlari = hesap_kodlari
            st.toast("Hesap kodları kaydedildi!", icon="✅")
    with col2:
        if st.button("Sıfırla", width="stretch"):
            st.session_state.hesap_kodlari = varsayilan_kodlar()
            dosya_yaz(HESAP_FILE, st.session_state.hesap_kodlari)
            st.rerun()

    st.divider()
    st.header("Ürün Kodları")
    if "urun_kodlari" not in st.session_state:
        st.session_state.urun_kodlari = urun_kodlari_yukle()

    with st.expander("Ürün Kodlarını Yönet", expanded=False):
        edited = st.data_editor(
            st.session_state.urun_kodlari,
            column_config={
                "pattern": "Ürün",
                "hesap_kodu": "Hesap Kodu",
                "aciklama": "Açıklama",
            },
            num_rows="dynamic",
            key="urun_kodlari_editor",
            width="stretch",
        )

        if st.button("Kaydet", width="stretch", type="primary"):
            st.session_state.urun_kodlari = edited
            urun_kodlari_kaydet([dict(k) for k in edited])
            st.toast("Ürün kodları kaydedildi!", icon="✅")

if sayfa == "Dashboard":
    st.header("Genel Bakış")
    
    tum_fisler = tum_fisleri_yukle()
    kayitlar = gecmis_listele()
    ml = mukellefler()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Kayıt", f"{len(kayitlar)}")
    c2.metric("Toplam Fiş", f"{len(tum_fisler)}")
    c3.metric("Aktif Mükellef", f"{len(ml)}")
    toplam_ciro = sum(f.get("net_toplam", 0) or 0 for f in tum_fisler)
    c4.metric("Toplam Ciro", f"{toplam_ciro:,.0f} TL")

    if tum_fisler:
        st.divider()
        st.subheader("Son 10 Fiş")
        son_fisler = sorted(tum_fisler, key=lambda x: x.get("tarih") or "", reverse=True)[:10]
        df = pd.DataFrame([{
            "Tarih": f.get("tarih", "?"), "Z No": f.get("z_no", "?"),
            "Firma": f.get("firma_adi", "") or f.get("mukellef", f.get("mukellef_adi", "")),
            "Banka": f.get("banka_adi", "") or "-",
            "Brüt": f.get("brut", 0), "Net": f.get("net_toplam", 0),
            "KK": f.get("kredi_karti", 0), "Nakit": f.get("nakit", 0),
            "Fiş İptal": f.get("iadeler", 0)
        } for f in son_fisler])
        st.dataframe(df, width="stretch", hide_index=True)

        st.divider()
        col_banka, col_mukellef = st.columns(2)
        with col_banka:
            st.subheader("Banka Bazlı Ciro")
            banka_ciro = {}
            for f in tum_fisler:
                b = f.get("banka_adi", "") or "Belirsiz/Nakit"
                banka_ciro[b] = banka_ciro.get(b, 0) + (f.get("net_toplam", 0) or 0)
            df_b = pd.DataFrame([{"Banka": k, "Toplam Ciro": v} for k, v in sorted(banka_ciro.items(), key=lambda x: -x[1])])
            st.dataframe(df_b, width="stretch", hide_index=True)

        with col_mukellef:
            st.subheader("Mükellef Bazlı Ciro")
            musteri_ciro = {}
            for f in tum_fisler:
                m = f.get("mukellef", "") or f.get("mukellef_adi", "") or "Bilinmeyen"
                musteri_ciro[m] = musteri_ciro.get(m, 0) + (f.get("net_toplam", 0) or 0)
            df_m = pd.DataFrame([{"Mükellef": k, "Toplam Ciro": v} for k, v in sorted(musteri_ciro.items(), key=lambda x: -x[1])])
            st.dataframe(df_m, width="stretch", hide_index=True)

elif sayfa == "Z Raporu Yükle":
    st.header("Z Raporu Fotoğraf Yükleme ve OCR")

    urun_kodlari = st.session_state.get("urun_kodlari", [])

    ml = mukellefler()
    secili_mukellef = ""
    if ml:
        secili_mukellef = st.selectbox("Mükellef Seç (isteğe bağlı)", ["(Mükellef yok)"] + [m["adi"] for m in ml])
        if secili_mukellef == "(Mükellef yok)":
            secili_mukellef = ""



    uploaded_files = st.file_uploader("Z raporu/fiş seç (JPG/PNG/PDF)", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)

    if uploaded_files:
        pdf_count = sum(1 for f in uploaded_files if f.name.lower().endswith(".pdf"))
        img_count = len(uploaded_files) - pdf_count
        st.success(f"{img_count} görsel, {pdf_count} PDF yüklendi")
        cols = st.columns(5)
        for i, f in enumerate(uploaded_files):
            with cols[i % 5]:
                if f.name.lower().endswith(".pdf"):
                    st.caption(f"📄 {f.name[:20]}")
                else:
                    img = Image.open(f)
                    st.image(img, caption=f.name[:20], width="stretch")
                    f.seek(0)

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        run_ocr = st.button("HEPSİNİ OKU (OCR)", type="primary", width="stretch", disabled=not uploaded_files or ocr_engine is None)
    with col_b2:
        if st.button("Temizle", width="stretch"):
            for k in ["results", "processed"]:
                st.session_state.pop(k, None)
            st.rerun()

    if run_ocr and uploaded_files:
        import time as _time
        from pdf2image import convert_from_bytes
        all_results = []
        toplam = len(uploaded_files)
        progress = st.progress(0, text="OCR yapılıyor...")
        baslama = _time.time()

        for i, uf in enumerate(uploaded_files):
            uf.seek(0)
            try:
                data = uf.read()
                if uf.name.lower().endswith(".pdf"):
                    pages = convert_from_bytes(data, dpi=300)
                    for pi, page in enumerate(pages):
                        ocr_text = ocr_image(page.convert("RGB"))
                        parsed = parse_z_raporu(ocr_text)
                        parsed["filename"] = f"{uf.name} - Syf {pi+1}"
                        parsed["ocr_text"] = ocr_text
                        parsed["mukellef_adi"] = secili_mukellef
                        all_results.append(parsed)
                else:
                    img = Image.open(io.BytesIO(data))
                    ocr_text = ocr_image(img)
                    parsed = parse_z_raporu(ocr_text)
                    parsed["filename"] = uf.name
                    parsed["ocr_text"] = ocr_text
                    parsed["mukellef_adi"] = secili_mukellef
                    all_results.append(parsed)
            except Exception as e:
                log.error(f"OCR hatasi {uf.name}: {e}")
                all_results.append({"filename": uf.name, "error": str(e), "ocr_text": ""})
            gecen = _time.time() - baslama
            ort = gecen / max(i + 1, 1)
            kal = max(toplam - i - 1, 0) * ort
            kstr = f"{int(kal//60)}d {int(kal%60)}s" if kal >= 60 else f"{int(kal)}s"
            gstr = f"{int(gecen//60)}d {int(gecen%60)}s" if gecen >= 60 else f"{int(gecen)}s"
            progress.progress((i + 1) / max(toplam, 1), text=f"{i+1}/{toplam} | {gstr} | ~{kstr}")

        st.session_state.results = all_results
        st.session_state.processed = True
        try:
            gecmis_kaydet(all_results, hesap_kodlari, secili_mukellef)
        except Exception as e:
            log.error(f"Gecmis kaydedilemedi: {e}")
        try:
            otomatik_yedekle()
        except Exception as e:
            log.error(f"Otomatik yedek hatası: {e}")
        basarili = sum(1 for r in all_results if "error" not in r)
        hatali = len(all_results) - basarili
        if hatali > 0:
            st.warning(f"{basarili} başarılı, {hatali} hatalı")
        else:
            st.success(f"{len(all_results)} Z raporu işlendi ve kaydedildi!")
        st.rerun()

    if st.session_state.get("processed") and st.session_state.results:
        results = st.session_state.results
        st.divider()
        st.subheader(f"Sonuçlar ({len(results)} Z Raporu)")

        ozet_data = []
        all_luca_rows = []
        fc = 1
        for i, r in enumerate(results):
            if "error" in r:
                ozet_data.append({"#": i+1, "Dosya": r["filename"], "Durum": "HATA", "Tarih": "", "Z No": "", "Firma": "", "Banka": "", "Brüt": 0, "Net": 0, "KK": 0, "Nakit": 0, "İptal": 0})
                continue
            try:
                rows = data_to_luca_rows(r, hesap_kodlari, fc, urun_kodlari)
                all_luca_rows.extend(rows)
                fc += 1
            except Exception as e:
                log.error(f"LUCA satır hatası {r.get('filename','')}: {e}")
                st.error(f"Satır hatası {r.get('filename','')}: {e}")
                rows = []
            ozet_data.append({
                "#": i+1, "Dosya": r.get("filename", "")[:25], "Durum": "OK",
                "Tarih": r.get("tarih", "?"), "Z No": r.get("z_no", "?"),
                "Firma": r.get("firma_adi", "") or "-",
                "Banka": r.get("banka_adi", "") or "-",
                "Brüt": r.get("brut", 0), "Net": r.get("net_toplam", 0),
                "KK": r.get("kredi_karti", 0), "Nakit": r.get("nakit", 0),
                "İptal": r.get("iadeler", 0),
            })

        st.dataframe(pd.DataFrame(ozet_data), width="stretch", hide_index=True)

        iade_eksik = []
        for i, r in enumerate(results):
            if "error" not in r:
                iade_eksik.append((i, r))

        if iade_eksik:
            with st.expander("Fiş İptal / İade Varsa Girin (Opsiyonel)", expanded=False):
                for idx, r in iade_eksik:
                    session_key = f"iade_{idx}"
                    if session_key not in st.session_state:
                        st.session_state[session_key] = float(r.get("iadeler", 0))
                    col1, col2 = st.columns([3, 2])
                    with col1:
                        st.text(f"{r.get('filename','')} — Brüt: {r.get('brut',0):,.2f} TL")
                    with col2:
                        st.number_input(
                            f"İptal Tutarı (TL)",
                            min_value=0.0,
                            step=100.0,
                            key=session_key,
                            help="Fiş iptali/iade tutarı varsa girin, yoksa 0 bırakın"
                        )
                if st.button("İade Tutarlarını Kaydet", type="primary", use_container_width=True):
                    for idx, r in iade_eksik:
                        r["iadeler"] = st.session_state.get(f"iade_{idx}", 0)
                    st.toast("İade tutarları kaydedildi!", icon="✅")
                    st.rerun()

        duzeltilebilir = [(i, r) for i, r in enumerate(results) if "error" not in r]
        if duzeltilebilir:
            with st.expander("Sonuçları Düzenle (Tarih, Tutar, KDV)", expanded=False):
                for idx, r in duzeltilebilir:
                    st.markdown(f"**{idx+1}. {r.get('filename','')}**")

                    def tarih_degistir(_r=r, _key=f"ed_tarih_{idx}"):
                        _r["tarih"] = st.session_state[_key] if st.session_state[_key] else None

                    def brut_degistir(_r=r, _key=f"ed_brut_{idx}"):
                        val = st.session_state[_key]
                        if val > 0:
                            _r["brut"] = val
                            if _r["net_toplam"] == 0 or _r["net_toplam"] == _r.get("brut", 0):
                                _r["net_toplam"] = val
                            if _r["toplam_tahsilat"] == 0:
                                _r["toplam_tahsilat"] = val

                    def nakit_degistir(_r=r, _key=f"ed_nakit_{idx}"):
                        _r["nakit"] = st.session_state[_key]

                    def kk_degistir(_r=r, _key=f"ed_kk_{idx}"):
                        _r["kredi_karti"] = st.session_state[_key]

                    def yemek_degistir(_r=r, _key=f"ed_yemek_{idx}"):
                        _r["yemek_ceki"] = st.session_state[_key]

                    def net_degistir(_r=r, _key=f"ed_net_{idx}"):
                        _r["net_toplam"] = st.session_state[_key]

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        tarih_val = r.get("tarih") or ""
                        st.text_input("Tarih (GG.AA.YYYY)", value=tarih_val,
                                      key=f"ed_tarih_{idx}", on_change=tarih_degistir)
                    with c2:
                        st.number_input("Brüt (TL)", min_value=0.0, value=float(r.get("brut", 0)),
                                        step=100.0, key=f"ed_brut_{idx}", on_change=brut_degistir)
                    with c3:
                        st.number_input("Net (TL)", min_value=0.0, value=float(r.get("net_toplam", 0)),
                                        step=100.0, key=f"ed_net_{idx}", on_change=net_degistir)

                    c4, c5, c6 = st.columns(3)
                    with c4:
                        st.number_input("Nakit (TL)", min_value=0.0, value=float(r.get("nakit", 0)),
                                        step=100.0, key=f"ed_nakit_{idx}", on_change=nakit_degistir)
                    with c5:
                        st.number_input("Kredi Kartı (TL)", min_value=0.0, value=float(r.get("kredi_karti", 0)),
                                        step=100.0, key=f"ed_kk_{idx}", on_change=kk_degistir)
                    with c6:
                        st.number_input("Yemek Çeki (TL)", min_value=0.0, value=float(r.get("yemek_ceki", 0)),
                                        step=100.0, key=f"ed_yemek_{idx}", on_change=yemek_degistir)

                    if idx < len(duzeltilebilir) - 1:
                        st.divider()

        kdv_eksik = [(i, r) for i, r in enumerate(results) if "error" not in r and not r.get("kdv_kalemleri")]
        if kdv_eksik:
            st.warning(f"{len(kdv_eksik)} Z raporunda KDV oranı bulunamadı. Excel için KDV oranı seçin:")
            for idx, r in kdv_eksik:
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    st.text(f"{r.get('filename','')} — Brüt: {r.get('brut',0):,.2f} TL")
                with col2:
                    secenekler = ["%1", "%10", "%20", "Özel"]
                    secim = st.selectbox(f"KDV Oranı", secenekler, key=f"kdv_oran_{idx}")
                with col3:
                    if secim == "Özel":
                        ozel_oran = st.number_input(f"KDV %", min_value=0, max_value=100, value=20, key=f"ozel_{idx}")
                        oran = ozel_oran
                    else:
                        oran = int(secim.replace("%", ""))
                        st.metric("Oran", f"%{oran}")
                with col4:
                    st.write("")
                    st.write("")
                    if st.button("Uygula", key=f"kdv_uygula_{idx}"):
                        tutar = r.get("brut", 0) or r.get("net_toplam", 0)
                        net_tutar = round(tutar / (1 + oran / 100), 2)
                        kdv_tutar = round(tutar - net_tutar, 2)
                        r["kdv_kalemleri"] = [{"oran": oran, "matrah": net_tutar, "kdv_tutari": kdv_tutar}]
                        st.rerun()
            st.info("KDV oranlarını tamamlayıp sayfayı yenileyin.")
            st.stop()

        # Tüm hesaplamalar tek merkezden
        all_luca_rows = hesapla_luca_rows(results, hesap_kodlari, urun_kodlari)
        
        toplam_borc = sum(r.get("Borç", 0) or 0 for r in all_luca_rows)
        toplam_alacak = sum(r.get("Alacak", 0) or 0 for r in all_luca_rows)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Z Raporu", f"{len(results)}")
        c2.metric("Fiş Satırı", f"{len(all_luca_rows)}")
        c3.metric("Toplam Borç", f"{toplam_borc:,.2f}")
        c4.metric("Toplam Alacak", f"{toplam_alacak:,.2f}")

        if abs(toplam_borc - toplam_alacak) < 0.01:
            st.success("Borç = Alacak. DENGELİ.")
        else:
            st.warning(f"Fark: {abs(toplam_borc - toplam_alacak):,.2f} TL")

        st.divider()

        mod = st.session_state.get("mod", "Bilanço")
        if mod == "Serbest Meslek":
            muk_bilgi = None
            for m in mukellefler():
                if m.get("adi") == secili_mukellef:
                    muk_bilgi = m
                    break
            satirlar = []
            satirlar.append(";".join(BASIT_USUL_KOLONLAR))
            for r in results:
                if "error" in r:
                    continue
                evrak_tarihi = r.get("tarih", "")
                evrak_no = r.get("z_no", "") or r.get("belge_no", "")
                tckn = (muk_bilgi or {}).get("vergi_no", "")
                vd = (muk_bilgi or {}).get("vd", "")
                unvan = (muk_bilgi or {}).get("adi", "")
                adres = (muk_bilgi or {}).get("notlar", "")
                kk_tutar = r.get("kredi_karti", 0) or 0
                toplam_tahsilat = r.get("toplam_tahsilat", 0) or 1
                kk_orani = lambda b: round(b * kk_tutar / toplam_tahsilat, 2) if toplam_tahsilat > 0 else 0
                urunler = r.get("urunler", [])
                if not urunler:
                    row = [""] * len(BASIT_USUL_KOLONLAR)
                    row[0] = "1"
                    row[1] = "Defter Fişleri"
                    row[2] = "Z Raporu"
                    row[3] = evrak_tarihi
                    row[4] = evrak_tarihi
                    row[6] = evrak_no
                    row[7] = tckn
                    row[8] = vd
                    row[9] = unvan
                    row[11] = adres
                    brut = r.get("brut", 0) or toplam_tahsilat or 0
                    row[22] = brut
                    row[29] = brut
                    row[30] = kk_orani(brut)
                    satirlar.append(";".join(str(x) for x in row))
                    continue
                for urun in urunler:
                    row = [""] * len(BASIT_USUL_KOLONLAR)
                    row[0] = "1"
                    row[1] = "Defter Fişleri"
                    row[2] = "Z Raporu"
                    row[3] = evrak_tarihi
                    row[4] = evrak_tarihi
                    row[6] = evrak_no
                    row[7] = tckn
                    row[8] = vd
                    row[9] = unvan
                    row[11] = adres
                    ua = urun.get("urun", "")
                    miktar = urun.get("miktar", 0) or 0
                    brut_tutar = urun.get("tutar", 0) or 0
                    oran = urun.get("oran", 0) or 0
                    row[19] = ua
                    row[20] = miktar
                    row[21] = round(brut_tutar / miktar, 2) if miktar > 0 else ""
                    row[22] = round(brut_tutar / (1 + oran / 100), 2) if oran > 0 else brut_tutar
                    row[24] = oran
                    row[28] = round(brut_tutar - (brut_tutar / (1 + oran / 100)), 2) if oran > 0 else 0
                    row[29] = brut_tutar
                    row[30] = kk_orani(brut_tutar)
                    satirlar.append(";".join(str(x) for x in row))
            csv_icerik = "\r\n".join(satirlar)
            csv_data = csv_icerik.encode("cp1254")
            basit_excel = generate_basit_usul_excel(results, muk_bilgi, st.session_state.get("luca_sabloni"))
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("XLSX İNDİR (Serbest Meslek)", basit_excel,
                    f"basit_usul_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary", use_container_width=True)
            with c2:
                st.download_button("CSV İNDİR (LUCA için)", csv_data,
                    f"basit_usul_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv", use_container_width=True)
        else:
            excel_data = generate_excel_cached(tuple(all_luca_rows))
            st.download_button("EXCEL İNDİR (LUCA)", excel_data,
                f"z_raporlari_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary", width="stretch")

        with st.expander("OCR Ham Metinler"):
            for i, r in enumerate(results):
                if "error" not in r:
                    st.markdown(f"**{i+1}. {r.get('filename','')} — Z No: {r.get('z_no','?')}**")
                    st.text(r.get("ocr_text", ""))
                    st.divider()

elif sayfa == "Fiş Geçmişi":
    st.header("Fiş Geçmişi")
    urun_kodlari = st.session_state.get("urun_kodlari", [])

    tum_fisler = tum_fisleri_yukle()

    if not tum_fisler:
        st.info("Henüz fiş yok. Z Raporu Yükle sayfasından fiş ekleyin.")
    else:
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            tarih_basla = st.date_input("Başlangıç", value=datetime.now() - timedelta(days=30))
        with col_f2:
            tarih_bitis = st.date_input("Bitiş", value=datetime.now())
        with col_f3:
            ml = mukellefler()
            filtre_mukellef = st.selectbox("Mükellef", ["Tümü"] + [m["adi"] for m in ml])
        with col_f4:
            tum_bankalar = sorted(set(f.get("banka_adi", "") or "" for f in tum_fisler if f.get("banka_adi")))
            filtre_banka = st.selectbox("Banka", ["Tümü"] + tum_bankalar)

        filtered = []
        for f in tum_fisler:
            tarih_str = f.get("tarih", "")
            try:
                tarih_obj = datetime.strptime(tarih_str, "%d.%m.%Y").date()
                if not (tarih_basla <= tarih_obj <= tarih_bitis):
                    continue
            except (ValueError, TypeError):
                if tarih_str:
                    continue
            if filtre_mukellef != "Tümü":
                m = f.get("mukellef", "") or f.get("mukellef_adi", "")
                if m != filtre_mukellef:
                    continue
            if filtre_banka != "Tümü":
                b = f.get("banka_adi", "") or ""
                if b != filtre_banka:
                    continue
            filtered.append(f)

        st.info(f"{len(filtered)} fiş bulundu")

        if filtered:
            df = pd.DataFrame([{
                "Tarih": f.get("tarih", "?"), "Z No": f.get("z_no", "?"),
                "Firma": f.get("firma_adi", "") or f.get("mukellef", f.get("mukellef_adi", "")),
                "Banka": f.get("banka_adi", "") or "-",
                "Brüt": f.get("brut", 0), "Net": f.get("net_toplam", 0),
                "KK": f.get("kredi_karti", 0), "Nakit": f.get("nakit", 0),
                "İptal": f.get("iadeler", 0),
            } for f in filtered])
            st.dataframe(df, width="stretch", hide_index=True)

            mod = st.session_state.get("mod", "Bilanço")
            if mod == "Serbest Meslek":
                muk_bilgi = None
                for m in mukellefler():
                    if m.get("adi") == secili_mukellef:
                        muk_bilgi = m
                        break
                basit_excel = generate_basit_usul_excel(filtered, muk_bilgi, st.session_state.get("luca_sabloni"))
                st.download_button("Seçilenlerden Excel Oluştur (Serbest Meslek)", basit_excel,
                    f"basit_usul_filtre_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch")
            else:
                all_luca = []
                fc = 1
                for f in filtered:
                    all_luca.extend(data_to_luca_rows(f, hesap_kodlari, fc, urun_kodlari))
                    fc += 1
                excel_data = generate_excel(all_luca)
                st.download_button("Seçilenlerden Excel Oluştur (LUCA)", excel_data,
                    f"filtrelenmis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch")

elif sayfa == "Mükellef Yönetimi":
    st.header("Mükellef Yönetimi")

    ml = mukellefler()

    with st.expander("Yeni Mükellef Ekle", expanded=not ml):
        with st.form("mukellef_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                adi = st.text_input("Mükellef Adı", placeholder="Örn: Ahmet Mağazacılık Ltd.")
                vergi_no = st.text_input("Vergi No", placeholder="1234567890")
            with col_b:
                vd = st.text_input("Vergi Dairesi", placeholder="Örn: Kartal VD")
                telefon = st.text_input("Telefon", placeholder="0532 xxx xx xx")
            notlar = st.text_area("Notlar", placeholder="Ek bilgiler...")
            submitted = st.form_submit_button("Ekle", type="primary")
            if submitted and adi:
                ml.append({
                    "adi": adi, "vergi_no": vergi_no, "vd": vd,
                    "telefon": telefon, "notlar": notlar,
                    "olusturma": datetime.now().strftime("%d.%m.%Y")
                })
                dosya_yaz(MUKELLEF_FILE, ml)
                st.success(f"{adi} eklendi!")
                st.rerun()

    if ml:
        st.divider()
        st.subheader(f"Kayıtlı Mükellefler ({len(ml)})")
        for i, m in enumerate(ml):
            with st.expander(f"{m['adi']} — {m.get('vergi_no', '?')}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Vergi Dairesi:** {m.get('vd', '?')}")
                c2.write(f"**Telefon:** {m.get('telefon', '?')}")
                c3.write(f"**Kayıt:** {m.get('olusturma', '?')}")
                if m.get("notlar"):
                    st.write(f"Not: {m['notlar']}")

                if st.button("Sil", key=f"sil_{i}", width="stretch"):
                    ml.pop(i)
                    dosya_yaz(MUKELLEF_FILE, ml)
                    st.rerun()
    else:
        st.info("Henüz mükellef eklenmemiş.")

elif sayfa == "KDV Özeti":
    st.header("Dönemsel KDV Özeti")
    urun_kodlari = st.session_state.get("urun_kodlari", [])

    tum_fisler = tum_fisleri_yukle()
    if not tum_fisler:
        st.info("Henüz fiş yok.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            ay = st.selectbox("Ay", range(1, 13), index=datetime.now().month - 1)
        with col2:
            yil = st.selectbox("Yıl", range(datetime.now().year, datetime.now().year - 3, -1))

        ay_fisler = []
        for f in tum_fisler:
            try:
                t = datetime.strptime(f.get("tarih", ""), "%d.%m.%Y")
                if t.month == ay and t.year == yil:
                    ay_fisler.append(f)
            except (ValueError, TypeError):
                pass

        if not ay_fisler:
            st.warning(f"{ay:02d}/{yil} döneminde fiş bulunamadı.")
        else:
            st.success(f"{len(ay_fisler)} fiş bulundu ({ay:02d}/{yil})")

            kdv_toplamlari = {}
            toplam_ciro = 0
            toplam_kk = 0
            toplam_nakit = 0
            toplam_iptal = 0

            for f in ay_fisler:
                toplam_ciro += f.get("net_toplam", 0) or 0
                toplam_kk += f.get("kredi_karti", 0) or 0
                toplam_nakit += f.get("nakit", 0) or 0
                toplam_iptal += f.get("iadeler", 0) or 0

                for urun in f.get("urunler", []):
                    oran = urun.get("oran", 0)
                    tutar = urun.get("tutar", 0)
                    if oran > 0 and tutar > 0:
                        if oran not in kdv_toplamlari:
                            kdv_toplamlari[oran] = {"matrah": 0, "kdv": 0, "brut": 0}
                        net = round(tutar / (1 + oran / 100), 2)
                        kdv = round(tutar - net, 2)
                        kdv_toplamlari[oran]["matrah"] += net
                        kdv_toplamlari[oran]["kdv"] += kdv
                        kdv_toplamlari[oran]["brut"] += tutar

                for kv in f.get("kdv_kalemleri", []):
                    oran = kv.get("oran", 0)
                    if oran > 0 and oran not in kdv_toplamlari:
                        matrah = kv.get("matrah", 0) or 0
                        kdv_t = kv.get("kdv_tutari", 0) or 0
                        kdv_toplamlari[oran] = {"matrah": matrah, "kdv": kdv_t, "brut": round(matrah + kdv_t, 2)}

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Toplam Ciro", f"{toplam_ciro:,.0f} TL")
            c2.metric("Kredi Kartı", f"{toplam_kk:,.0f} TL")
            c3.metric("Nakit", f"{toplam_nakit:,.0f} TL")
            c4.metric("Fiş İptal", f"{toplam_iptal:,.0f} TL")

            if kdv_toplamlari:
                st.divider()
                st.subheader("KDV Dökümü")
                kdv_rows = []
                genel_kdv = 0
                for oran in sorted(kdv_toplamlari.keys()):
                    k = kdv_toplamlari[oran]
                    kdv_rows.append({
                        "KDV Oranı": f"%{oran}",
                        "Brüt Tutar": f"{k['brut']:,.2f}",
                        "Matrah": f"{k['matrah']:,.2f}",
                        "KDV Tutarı": f"{k['kdv']:,.2f}",
                    })
                    genel_kdv += k['kdv']
                st.dataframe(pd.DataFrame(kdv_rows), width="stretch", hide_index=True)
                st.metric("Toplam Hesaplanan KDV", f"{genel_kdv:,.2f} TL")

            mod = st.session_state.get("mod", "Bilanço")
            if mod == "Serbest Meslek":
                muk_bilgi = None
                for m in mukellefler():
                    if m.get("adi") == secili_mukellef:
                        muk_bilgi = m
                        break
                basit_excel = generate_basit_usul_excel(ay_fisler, muk_bilgi, st.session_state.get("luca_sabloni"))
                st.download_button(f"{ay:02d}/{yil} Serbest Meslek Excel", basit_excel,
                    f"basit_usul_{yil}_{ay:02d}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary", width="stretch")
            else:
                all_luca = []
                fc = 1
                for f in ay_fisler:
                    all_luca.extend(data_to_luca_rows(f, hesap_kodlari, fc, urun_kodlari))
                    fc += 1
                if all_luca:
                    excel_data = generate_excel(all_luca)
                    st.download_button(f"{ay:02d}/{yil} Luca Excel", excel_data,
                        f"luca_{yil}_{ay:02d}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary", width="stretch")

elif sayfa == "Ayarlar":
    st.header("Ayarlar")

    st.subheader("Yedekleme")
    col_y1, col_y2 = st.columns(2)
    with col_y1:
        if st.button("Yedek Oluştur", width="stretch", type="primary"):
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                yedek_klasor = os.path.join(YEDEK_KLASORU, f"yedek_{timestamp}")
                os.makedirs(yedek_klasor, exist_ok=True)
                for fp in [HESAP_FILE, MUKELLEF_FILE, URUN_KODLARI_FILE]:
                    if os.path.exists(fp):
                        shutil.copy2(fp, yedek_klasor)
                if os.path.exists(GECMIS_KLASORU):
                    shutil.copytree(GECMIS_KLASORU, os.path.join(yedek_klasor, "gecmis"), dirs_exist_ok=True)
                st.toast("Yedek oluşturuldu!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Yedek oluşturulamadı: {e}")

    with col_y2:
        yedekler = sorted(glob.glob(os.path.join(YEDEK_KLASORU, "yedek_*")), reverse=True)
        if yedekler:
            secilen_yedek = st.selectbox("Yedek Seç", yedekler)
            if st.button("Geri Yükle", width="stretch"):
                try:
                    for fp in glob.glob(os.path.join(secilen_yedek, "*.json")):
                        shutil.copy2(fp, DATA_DIR)
                    gecmis_hedef = os.path.join(secilen_yedek, "gecmis")
                    if os.path.exists(gecmis_hedef):
                        shutil.copytree(gecmis_hedef, GECMIS_KLASORU, dirs_exist_ok=True)
                    st.toast("Yedek geri yüklendi!", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Geri yükleme hatası: {e}")
        else:
            st.info("Henüz yedek yok")

    st.divider()
    st.subheader("Tehlikeli İşlemler")
    if "sil_onay" not in st.session_state:
        st.session_state.sil_onay = False
    if "fis_sil_onay" not in st.session_state:
        st.session_state.fis_sil_onay = False

    if not st.session_state.fis_sil_onay:
        if st.button("TÜM FİŞLERİ SİL", type="secondary"):
            st.session_state.fis_sil_onay = True
            st.rerun()
    else:
        st.warning("Tüm fişler silinecek! Mükellefler ve ayarlar kalacak.")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if st.button("EMİNİM, FİŞLERİ SİL!", type="primary", width="stretch"):
                try:
                    for fp in glob.glob(os.path.join(GECMIS_KLASORU, "*.json")):
                        os.remove(fp)
                    for fp in glob.glob(os.path.join(FISLER_KLASORU, "*")):
                        if os.path.isfile(fp):
                            os.remove(fp)
                        elif os.path.isdir(fp):
                            shutil.rmtree(fp, ignore_errors=True)
                    st.session_state.fis_sil_onay = False
                    st.toast("Tüm fişler silindi!", icon="🗑️")
                    st.rerun()
                except Exception as e:
                    st.error(f"Silme hatası: {e}")
        with col_f2:
            if st.button("İptal", type="secondary", width="stretch"):
                st.session_state.fis_sil_onay = False
                st.rerun()

    if not st.session_state.sil_onay:
        if st.button("TÜM VERİLERİ SİL", type="secondary"):
            st.session_state.sil_onay = True
            st.rerun()
    else:
        st.warning("Tüm veriler silinecek! Bu işlem geri alınamaz.")
        col_onay, col_iptal = st.columns(2)
        with col_onay:
            if st.button("EMİNİM, SİL!", type="primary", width="stretch"):
                try:
                    shutil.rmtree(GECMIS_KLASORU, ignore_errors=True)
                    shutil.rmtree(FISLER_KLASORU, ignore_errors=True)
                    os.makedirs(GECMIS_KLASORU, exist_ok=True)
                    os.makedirs(FISLER_KLASORU, exist_ok=True)
                    for fp in [HESAP_FILE, MUKELLEF_FILE]:
                        if os.path.exists(fp):
                            os.remove(fp)
                    st.session_state.sil_onay = False
                    st.toast("Tüm veriler silindi!", icon="🗑️")
                    st.rerun()
                except Exception as e:
                    st.error(f"Silme hatası: {e}")
        with col_iptal:
            if st.button("İptal", type="secondary", width="stretch"):
                st.session_state.sil_onay = False
                st.rerun()

    st.divider()
    st.subheader("Sistem Durumu")
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"Veri klasörü: `{DATA_DIR}`")
        st.write(f"Geçmiş sayısı: `{len(gecmis_listele())}`")
    with c2:
        st.write(f"Mükellef sayısı: `{len(mukellefler())}`")
        st.write(f"Toplam fiş: `{len(tum_fisleri_yukle())}`")
