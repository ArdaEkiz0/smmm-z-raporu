import os
import glob
import shutil
import logging
from datetime import datetime, timedelta
from functools import lru_cache

from config import (
    DATA_DIR, HESAP_FILE, GECMIS_KLASORU, MUKELLEF_FILE,
    FISLER_KLASORU, YEDEK_KLASORU, URUN_KODLARI_FILE, EMAIL_FILE
)
from utils import dosya_oku, dosya_yaz, parse_tutar

log = logging.getLogger("smmm.db")


def otomatik_yedekle():
    log.info("Otomatik yedekleme baslatiliyor")
    yedekler = sorted(glob.glob(os.path.join(YEDEK_KLASORU, "yedek_*")), reverse=True)
    while len(yedekler) > 10:
        shutil.rmtree(yedekler.pop(), ignore_errors=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    yedek_dizini = os.path.join(YEDEK_KLASORU, f"yedek_{timestamp}")
    os.makedirs(yedek_dizini, exist_ok=True)
    kopyalanan = 0
    for fp in [HESAP_FILE, MUKELLEF_FILE, URUN_KODLARI_FILE]:
        if os.path.exists(fp):
            shutil.copy2(fp, yedek_dizini)
            kopyalanan += 1
    if os.path.exists(GECMIS_KLASORU):
        shutil.copytree(GECMIS_KLASORU, os.path.join(yedek_dizini, "gecmis"), dirs_exist_ok=True)
    log.info("Yedekleme tamamlandi: %s (%d dosya)", yedek_dizini, kopyalanan)


def mukellefler():
    import streamlit as st
    @st.cache_data(ttl=30)
    def _yukle():
        return dosya_oku(MUKELLEF_FILE, [])
    return _yukle()


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
    """Z raporu sonuclarini gecmis klasorune kaydet, ogrenme yap.

    Returns:
        dict: {"dosya_kayit": bool, "ogrenme_hatasi": str|None, "dosya_yolu": str}
    """
    from ocr import parse_z_raporu, duzeltme_ogren, ogrenci_alan_bul
    sonuc = {"dosya_kayit": False, "ogrenme_hatasi": None, "dosya_yolu": None}

    if not results or not isinstance(results, list):
        raise ValueError("Sonuç listesi boş veya geçersiz")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dosya_yolu = os.path.join(GECMIS_KLASORU, f"kayit_{ts}.json")
    kayit = {
        "tarih": ts,
        "mukellef": mukellef_adi,
        "fisler": results,
    }

    # Aşama 1: Dosyaya yaz (en kritik - basarisiz olursa exception firlat)
    try:
        dosya_yaz(dosya_yolu, kayit)
        sonuc["dosya_kayit"] = True
        sonuc["dosya_yolu"] = dosya_yolu
        log.info("Fis kaydedildi: %s (%d fis)", dosya_yolu, len(results))
    except Exception as e:
        log.error("Dosya yazma basarisiz: %s - %s", dosya_yolu, str(e))
        raise

    # Aşama 2: Cache invalidate (dosya yazildi, simdi cache temizle)
    try:
        import streamlit as st
        for k in ["_fis_ver_version", "_fis_kayitlar", "_fis_tumu"]:
            st.session_state.pop(k, None)
    except Exception as e:
        log.warning("Cache invalidate basarisiz: %s", str(e))

    # Aşama 3: Ogrenme (istatistiksel ogrenme motoru ile)
    ogrenme_hatasi = None
    try:
        from ogrenme_cekirdigi import duzeltme_kaydet, alan_duzeltme_kaydet
        from ocr import parse_z_raporu, ogrenci_alan_bul

        for r in results:
            if "error" in r:
                continue
            ham = r.get("ocr_text", "") or r.get("ham_text", "")
            if not ham:
                continue
            try:
                orj_parsed = parse_z_raporu(ham)
            except Exception as e:
                ogrenme_hatasi = f"parse_z_raporu hatasi: {str(e)[:100]}"
                log.warning(f"OCR parse basarisiz, ogrenme atlaniyor: {e}")
                continue
            for alan in ["firma_adi", "tarih", "banka_adi", "z_no", "belge_no",
                         "brut", "net_toplam", "nakit", "kredi_karti"]:
                dogru = r.get(alan, "")
                eski = orj_parsed.get(alan, "")
                if dogru and eski and str(dogru).strip().upper() != str(eski).strip().upper():
                    try:
                        hali = ogrenci_alan_bul(ham, alan, dogru)
                        if hali and hali.upper() != str(dogru).upper():
                            duzeltme_kaydet(hali.strip(), str(dogru).strip(),
                                            alan_adi=alan, kaynak="manuel")
                            alan_duzeltme_kaydet(alan, str(eski).strip(), str(dogru).strip())
                    except Exception as e:
                        log.warning("Ogrenme hatasi (%s): %s", alan, str(e))
    except Exception as e:
        ogrenme_hatasi = str(e)
        log.error("Toplu ogrenme hatasi: %s", str(e))

    sonuc["ogrenme_hatasi"] = ogrenme_hatasi
    return sonuc


def _fis_veri_version():
    """Gecmis dosyalarinin degisip degismedigini kontrol et - hizli."""
    toplam = 0
    en_son = 0
    try:
        for fp in glob.glob(os.path.join(GECMIS_KLASORU, "kayit_*.json")):
            toplam += 1
            mtime = os.path.getmtime(fp)
            if mtime > en_son:
                en_son = mtime
    except OSError:
        pass
    return f"v{toplam}_{en_son}"

def gecmis_listele():
    import streamlit as st
    ver_version = _fis_veri_version()
    ss = st.session_state
    if ss.get("_fis_ver_version") == ver_version and "_fis_kayitlar" in ss:
        return ss["_fis_kayitlar"]
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
    ss["_fis_ver_version"] = ver_version
    ss["_fis_kayitlar"] = kayitlar
    return kayitlar


def tum_fisleri_yukle():
    import streamlit as st
    ver_version = _fis_veri_version()
    ss = st.session_state
    if ss.get("_fis_ver_version") == ver_version and "_fis_tumu" in ss:
        return ss["_fis_tumu"]
    tumu = []
    for kayit in gecmis_listele():
        for f in kayit.get("fisler", []):
            if "error" not in f:
                f["mukellef"] = kayit.get("mukellef", kayit.get("mukellef_adi", ""))
                tumu.append(f)
    ss["_fis_ver_version"] = ver_version
    ss["_fis_tumu"] = tumu
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
    import smtplib
    import email.utils
    from email.mime.text import MIMEText
    email_config = dosya_oku(EMAIL_FILE, {})
    if not email_config.get("gonderen") or not email_config.get("sifre"):
        log.warning("Email gonderilemedi: yapılandırma eksik")
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
        log.info("Email gonderildi: %s", konu)
        return True
    except Exception as e:
        log.error("Email hatasi: %s", str(e))
        return False


# ── Saglik Kontrolu ──

def saglik_kontrolu():
    """Sistem saglik durumunu kontrol et."""
    durum = {
        "disk_ok": True,
        "dosyalar_ok": True,
        "yedek_sayisi": 0,
        "gecmis_sayisi": 0,
        "hatalar": [],
    }

    # Disk kontrolu
    try:
        import shutil as _shutil
        toplam, kullanilmis, bos = _shutil.disk_usage(DATA_DIR)
        bos_orani = bos / toplam
        if bos_orani < 0.1:
            durum["hatalar"].append(f"Disk doluluk orani yuksek: %{bos_orani*100:.1f}")
            durum["disk_ok"] = False
    except Exception as e:
        durum["hatalar"].append(f"Disk kontrolu hatasi: {str(e)}")

    # Dosya kontrolu
    for fp in [HESAP_FILE, MUKELLEF_FILE]:
        if not os.path.exists(fp):
            durum["hatalar"].append(f"Eksik dosya: {os.path.basename(fp)}")

    # Yedek sayisi
    try:
        durum["yedek_sayisi"] = len(glob.glob(os.path.join(YEDEK_KLASORU, "yedek_*")))
    except Exception:
        pass

    # Gecmis sayisi
    try:
        durum["gecmis_sayisi"] = len(glob.glob(os.path.join(GECMIS_KLASORU, "kayit_*.json")))
    except Exception:
        pass

    durum["saglikli"] = len(durum["hatalar"]) == 0
    return durum
