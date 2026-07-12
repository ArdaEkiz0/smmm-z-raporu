import os
import re
import glob
import json
import shutil
import smtplib
import email.utils
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from config import (
    DATA_DIR, HESAP_FILE, GECMIS_KLASORU, MUKELLEF_FILE,
    FISLER_KLASORU, YEDEK_KLASORU, URUN_KODLARI_FILE, EMAIL_FILE
)
from utils import dosya_oku, dosya_yaz, parse_tutar, log


def otomatik_yedekle():
    yedekler = sorted(glob.glob(os.path.join(YEDEK_KLASORU, "yedek_*")), reverse=True)
    while len(yedekler) > 10:
        shutil.rmtree(yedekler.pop(), ignore_errors=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    yedek_dizini = os.path.join(YEDEK_KLASORU, f"yedek_{timestamp}")
    os.makedirs(yedek_dizini, exist_ok=True)
    for fp in [HESAP_FILE, MUKELLEF_FILE, URUN_KODLARI_FILE]:
        if os.path.exists(fp):
            shutil.copy2(fp, yedek_dizini)
    if os.path.exists(GECMIS_KLASORU):
        shutil.copytree(GECMIS_KLASORU, os.path.join(yedek_dizini, "gecmis"), dirs_exist_ok=True)


def mukellefler():
    return dosya_oku(MUKELLEF_FILE, [])


def _mukellef_eslestir(firma_adi, mukellef_listesi, ml=None):
    if not firma_adi or not mukellef_listesi:
        return None
    fa = firma_adi.upper().strip()
    for i, m in enumerate(mukellef_listesi):
        ad = m.get("adi", "").upper().strip()
        ka = m.get("kisa_adi", "").upper().strip()
        if fa == ad or fa == ka:
            return i
        if ad and (ad in fa or fa in ad):
            return i
    from ocr import turkce_normalize
    fa_norm = turkce_normalize(fa)
    for i, m in enumerate(mukellef_listesi):
        ad_norm = turkce_normalize(m.get("adi", "").upper().strip())
        ka_norm = turkce_normalize(m.get("kisa_adi", "").upper().strip())
        if fa_norm == ad_norm or fa_norm == ka_norm:
            return i
        if ad_norm and (ad_norm in fa_norm or fa_norm in ad_norm):
            return i
    return None


def gecmis_kaydet(results, hesap_kodlari, mukellef_adi=""):
    from ocr import parse_z_raporu, duzeltme_ogren, ogrenci_alan_bul
    if not results:
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    kayit = {
        "tarih": ts,
        "mukellef": mukellef_adi,
        "fisler": results,
    }
    dosya_yaz(os.path.join(GECMIS_KLASORU, f"kayit_{ts}.json"), kayit)
    for r in results:
        if "error" in r:
            continue
        ham = r.get("ocr_text", "") or r.get("ham_text", "")
        if not ham:
            continue
        orj_parsed = parse_z_raporu(ham)
        for alan in ["firma_adi", "tarih", "banka_adi"]:
            dogru = r.get(alan, "")
            eski = orj_parsed.get(alan, "")
            if dogru and dogru != eski:
                hali = ogrenci_alan_bul(ham, alan, dogru)
                if hali and hali.upper() != dogru.upper():
                    duzeltme_ogren(hali, dogru)


def gecmis_listele():
    kayitlar = []
    for fp in sorted(glob.glob(os.path.join(GECMIS_KLASORU, "kayit_*.json")), reverse=True):
        try:
            kayit = dosya_oku(fp, {})
            if kayit:
                kayit["_dosya"] = fp
                kayitlar.append(kayit)
        except Exception:
            log.warning("Geçmiş dosyası okunamadı: %s", fp, exc_info=True)
            continue
    return kayitlar


def tum_fisleri_yukle():
    tumu = []
    for kayit in gecmis_listele():
        for f in kayit.get("fisler", []):
            if "error" not in f:
                f["mukellef"] = kayit.get("mukellef", kayit.get("mukellef_adi", ""))
                tumu.append(f)
    return tumu


def fis_kayit_bul(tarih, z_no):
    for kayit in gecmis_listele():
        for f in kayit.get("fisler", []):
            if f.get("tarih") == tarih and str(f.get("z_no", "")) == str(z_no):
                return f, kayit
    return None, None


def fis_sil(tarih, z_no):
    for kayit in gecmis_listele():
        for f in kayit.get("fisler", []):
            if f.get("tarih") == tarih and str(f.get("z_no", "")) == str(z_no):
                kayit["fisler"].remove(f)
                dosya_yaz(kayit["_dosya"], kayit)
                return True
    return False


def toplu_fis_sil(secim):
    silinen = 0
    for kayit in gecmis_listele():
        dosya = kayit["_dosya"]
        once = len(kayit.get("fisler", []))
        kayit["fisler"] = [f for f in kayit["fisler"] if f not in secim]
        sonra = len(kayit["fisler"])
        if sonra < once:
            silinen += once - sonra
            dosya_yaz(dosya, kayit)
    return silinen


def fis_guncelle(fis, yeni_veriler):
    for kayit in gecmis_listele():
        for f in kayit.get("fisler", []):
            if f is fis:
                f.update(yeni_veriler)
                dosya_yaz(kayit["_dosya"], kayit)
                return True
    return False


def kdv_ogren(results, urun_kodlari):
    from luca import urun_kodu_bul
    ogrenilen = {}
    for r in results:
        if "error" in r:
            continue
        for urun in r.get("urunler", []):
            ua = urun.get("urun", "")
            if not ua:
                continue
            oran = urun.get("oran", 0)
            if oran <= 0:
                continue
            eslesme = urun_kodu_bul(urun_kodlari, ua)
            if eslesme:
                mevcut_oran = eslesme.get("kdv_orani", 0)
                if mevcut_oran != oran:
                    eslesme["kdv_orani"] = oran
                    ogrenilen[ua] = oran
    if ogrenilen:
        from luca import urun_kodlari_kaydet
        urun_kodlari_kaydet(urun_kodlari)


def email_gonder(konu, icerik):
    email_config = dosya_oku(EMAIL_FILE, {})
    if not email_config.get("gonderen") or not email_config.get("sifre"):
        return False
    try:
        msg = MIMEText(icerik, "plain", "utf-8")
        msg["Subject"] = konu
        msg["From"] = email_config["gonderen"]
        msg["To"] = email_config.get("alici", email_config["gonderen"])
        msg["Date"] = email.utils.formatdate(localtime=True)
        with smtplib.SMTP(email_config.get("smtp_server", "smtp.gmail.com"), email_config.get("port", 587)) as server:
            server.starttls()
            server.login(email_config["gonderen"], email_config["sifre"])
            server.send_message(msg)
        return True
    except Exception as e:
        log.error(f"Email hatası: {e}")
        return False
