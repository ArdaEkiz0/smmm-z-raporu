import streamlit as st
import re
import os
import json
import logging
import sys
from datetime import datetime, timedelta
import requests

from config import (
    AUTH_FILE, HESAP_FILE, GECMIS_KLASORU, MUKELLEF_FILE, SABLON_FILE,
    OGRENILEN_SOZLUK, DUZELTME_SOZLUK, YEDEK_KLASORU, DATA_DIR,
    FISLER_KLASORU, GOT_OCR_API, EMAIL_FILE,
    URUN_KODLARI_FILE
)
from utils import dosya_oku, dosya_yaz, log
from ocr import ocr_engine, got_ocr_api_saglik
from veritabani import (
    mukellefler, gecmis_listele, tum_fisleri_yukle,
    otomatik_yedekle
)
from luca import (
    urun_kodlari_yukle, urun_kodlari_kaydet, varsayilan_kodlar
)
from pages import (
    _page_dashboard, _page_z_raporu_yukle, _page_fis_gecmisi,
    _page_mukellef_yonetimi, _page_kdv_ozeti, _page_ayarlar,
    _page_beyanname_takvimi, _page_efatura_sorgu
)
from tema import tema_uygula, tema_degistirici


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("smmm")

import traceback as _tb
def _global_excepthook(exc_type, exc_value, exc_tb):
    _msg = "".join(_tb.format_exception(exc_type, exc_value, exc_tb))
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash_log.txt"), "a", encoding="utf-8") as _f:
            _f.write(f"\n=== {datetime.now().isoformat()} ===\n{_msg}\n")
    except Exception:
        log.warning("Crash log dosyası yazılamadı", exc_info=True)
    sys.stderr.write(_msg)
sys.excepthook = _global_excepthook

st.set_page_config(page_title="SMMM Z Raporu Sistemi", layout="wide", page_icon="📒")

_zaman = datetime.now().strftime("%Y-%m-%d %H:%M")
st.caption(f"<span style='font-size:0.7rem;color:#94a3b8;'>v3.1 | {_zaman}</span>", unsafe_allow_html=True)

# Tarayici cache bypass
st.markdown("""
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
""", unsafe_allow_html=True)

# Eski ogrenme verilerini istatistiksel motora tasi
try:
    from ogrenme_cekirdigi import mevcut_sozlukleri_birlestir
    mevcut_sozlukleri_birlestir()
except Exception:
    pass

def _mevcut_kullanici():
    """Session state'den aktif kullaniciyi al."""
    return st.session_state.get("current_user")


def auth_ok():
    cu = _mevcut_kullanici()
    return bool(cu and cu.get("username"))


def _login_ekrani_goster():
    """Kullanici giris ekrani."""
    from user_manager import kullanici_dogrula, kullanicilari_yukle, DEFAULT_ADMIN_USERNAME

    st.markdown("""
    <div style="text-align:center;padding:2rem 0 1rem 0;">
        <div style="font-size:2.5rem;font-weight:800;letter-spacing:-0.03em;
                    background:linear-gradient(135deg,#0F766E,#14B8A6);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                    background-clip:text;">SMMM</div>
        <div style="font-size:0.9rem;color:#64748b;margin-top:0.3rem;">Z Raporu ve Fiş Yönetim Sistemi</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Kullanıcı Girişi")
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Kullanıcı Adı", placeholder="admin", key="login_username")
            password = st.text_input("Şifre", type="password", placeholder="••••••••", key="login_password")
            submit = st.form_submit_button("🔓 Giriş Yap", type="primary", use_container_width=True)

        if submit:
            if not username or not password:
                st.error("Kullanıcı adı ve şifre gerekli")
            else:
                user = kullanici_dogrula(username, password)
                if user:
                    st.session_state.current_user = {
                        "username": user.get("username"),
                        "role": user.get("role", "user"),
                        "full_name": user.get("full_name", user.get("username")),
                        "email": user.get("email", ""),
                    }
                    st.success(f"Hoş geldiniz, {user.get('full_name', user.get('username'))}!")
                    st.rerun()
                else:
                    st.error("Kullanıcı adı veya şifre hatalı")

        try:
            toplam = len(kullanicilari_yukle())
            st.caption(f"💡 İlk kurulum: **{DEFAULT_ADMIN_USERNAME}** / **admin123** (kullanıcı sayısı: {toplam})")
        except Exception:
            pass

        st.divider()
        if st.button("🔑 Şifremi Unuttum — Admin Şifresini Sıfırla", type="secondary", use_container_width=True, key="sifre_sifirla"):
            from user_manager import admin_sifirla
            sonuc = admin_sifirla()
            if sonuc["basarili"]:
                st.success(f"✅ {sonuc['mesaj']}. Artık **admin** / **admin123** ile giriş yapabilirsiniz.")
            else:
                st.error(sonuc["mesaj"])


if not auth_ok():
    _login_ekrani_goster()
    st.stop()

if "mod" not in st.session_state:
    st.session_state.mod = "Bilanço"

if "tema" not in st.session_state:
    st.session_state.tema = "light"

tema_uygula()

for klasor in [GECMIS_KLASORU, FISLER_KLASORU, YEDEK_KLASORU]:
    os.makedirs(klasor, exist_ok=True)

st.title("📊 SMMM Z Raporu ve Fiş Yönetim Sistemi")
st.caption("Akıllı OCR · LUCA/Logo/Netsis Export · Bilanço & Serbest Meslek")

with st.sidebar:
    if not st.session_state.get("_sidebar_brand_done"):
        st.markdown("""
        <div style="text-align:center;padding:1rem 0 0.5rem 0;line-height:1.1;">
            <div style="font-size:1.8rem;font-weight:800;letter-spacing:-0.02em;
                        background:linear-gradient(135deg,#0F766E,#14B8A6);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                        background-clip:text;line-height:1.1;display:block;">SMMM</div>
            <div style="font-size:0.7rem;color:#94a3b8;letter-spacing:0.08em;
                        text-transform:uppercase;margin-top:0.3rem;display:block;line-height:1.1;">Z Raporu Sistemi</div>
        </div>""", unsafe_allow_html=True)
        st.session_state["_sidebar_brand_done"] = True
    st.divider()
    _sayfa_ikon = {"Dashboard": "📊", "Z Raporu Yükle": "📄", "Fiş Geçmişi": "📋",
                   "Mükellef Yönetimi": "👤", "KDV Özeti": "🧾", "Ayarlar": "⚙️",
                   "Beyanname Takvimi": "📅", "E-Fatura Sorgu": "🧾"}
    sayfa = st.radio(
        "Sayfa Seç",
        list(_sayfa_ikon.keys()),
        format_func=lambda x: f"{_sayfa_ikon.get(x, '')} {x}",
        label_visibility="collapsed",
    )

    _cu = _mevcut_kullanici()
    if _cu:
        st.divider()
        rol_ikon = "👑" if _cu.get("role") == "admin" else "👤"
        st.markdown(
            f"<div style='padding:0.5rem;background:rgba(15,118,110,0.08);"
            f"border-radius:8px;font-size:0.85rem;'>"
            f"{rol_ikon} <b>{_cu.get('full_name', _cu.get('username'))}</b><br>"
            f"<span style='color:#64748b;font-size:0.75rem;'>@{_cu.get('username')}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button("🚪 Çıkış Yap", key="logout_btn", use_container_width=True):
            for k in ["current_user", "auth_ok", "_fis_ver_version",
                       "_fis_kayitlar", "_fis_tumu", "_sidebar_brand_done", "_tema_uygulandi"]:
                st.session_state.pop(k, None)
            st.rerun()

    tema_degistirici()

    st.divider()
    st.header("OCR Motoru")
    ocr_modu = st.session_state.get("ocr_modu", "Tesseract")
    ocr_secenek = st.radio("OCR Motoru Seç", ["Tesseract", "GOT-OCR API"], index=0 if ocr_modu == "Tesseract" else 1, label_visibility="collapsed")
    st.session_state.ocr_modu = ocr_secenek
    if ocr_secenek == "Tesseract":
        if ocr_engine:
            st.success("Tesseract OCR hazir", icon="🟢")
        else:
            st.error("Tesseract OCR bulunamadi! packages.txt kontrol edin.", icon="🔴")
    else:
        api_url = st.session_state.get(GOT_OCR_API, "")
        yeni_url = st.text_input("GOT-OCR API URL", value=api_url, placeholder="https://xxx.trycloudflare.com", label_visibility="collapsed", key="got_api_url_input")
        if yeni_url != api_url:
            if yeni_url and not yeni_url.startswith("http"):
                st.warning("URL http:// veya https:// ile baslamali")
            else:
                st.session_state[GOT_OCR_API] = yeni_url
        if yeni_url:
            @st.cache_data(ttl=60)
            def _saglik_kontrol(url):
                return got_ocr_api_saglik(url)
            saglik = _saglik_kontrol(yeni_url)
            if saglik:
                st.success("GOT-OCR API bagli", icon="🟢")
            else:
                st.warning("GOT-OCR API baglanamiyor! Kaggle/Colab notebook'unu calistirin.", icon="🟡")

    st.divider()
    st.header("Mükellef")
    ml = mukellefler()
    mevcut_mod = st.session_state.get("mod", "Bilanço")
    secili_mod = st.radio("Muhasebe Türü", ["Bilanço", "Serbest Meslek"], index=0 if mevcut_mod == "Bilanço" else 1, label_visibility="collapsed", key="mod_radio")
    st.session_state.mod = secili_mod

    def _mod_eslesir(m, secili):
        m_mod = m.get("mod", "Serbest Meslek")
        if secili == "Bilanço":
            return "Bilan" in m_mod
        return "Serbest" in m_mod or m_mod == "Serbest Meslek"

    filtreli_ml = [m for m in ml if _mod_eslesir(m, secili_mod)]
    muk_ad_listesi = ["(Genel)"] + [m.get("kisa_adi", m["adi"]) for m in filtreli_ml]
    onceki_idx = 0
    if "secili_mukellef" in st.session_state and st.session_state.secili_mukellef:
        for i, m in enumerate(filtreli_ml):
            if m.get("adi", "") == st.session_state.secili_mukellef:
                onceki_idx = i + 1
                break
    secili_kisa = st.selectbox("Mükellef Seç", muk_ad_listesi, index=onceki_idx, label_visibility="collapsed", key="muk_select")
    if secili_kisa != "(Genel)" and secili_kisa:
        for m in filtreli_ml:
            if m.get("kisa_adi", m["adi"]) == secili_kisa:
                st.session_state.secili_mukellef = m["adi"]
                st.session_state.secili_mukellef_kisa = secili_kisa
                break
    else:
        st.session_state.secili_mukellef = ""
        st.session_state.secili_mukellef_kisa = "(Genel)"

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
        if st.button("Şablonu Kaldır", key="sablon_kaldir"):
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
    hesap_kodlari = dict(st.session_state.hesap_kodlari)
    with st.expander("Hesap Kodları", expanded=False):
        for key, label in kod_etiketleri:
            hesap_kodlari[key] = st.text_input(label, value=st.session_state.hesap_kodlari.get(key, ""), key=f"hk_{key}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Kaydet", width="stretch", key="hk_kaydet"):
                dosya_yaz(HESAP_FILE, hesap_kodlari)
                st.session_state.hesap_kodlari = dict(hesap_kodlari)
                st.toast("Hesap kodları kaydedildi!", icon="✅")
        with col2:
            if st.button("Sıfırla", width="stretch", key="hk_sifirla"):
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

        if st.button("Kaydet", width="stretch", type="primary", key="uk_kaydet"):
            st.session_state.urun_kodlari = edited
            urun_kodlari_kaydet([dict(k) for k in edited])
            st.toast("Ürün kodları kaydedildi!", icon="✅")

sayfa_key = sayfa

if sayfa_key == "Dashboard":
    _page_dashboard()

elif sayfa_key == "Z Raporu Yükle":
    _page_z_raporu_yukle(hesap_kodlari)

elif sayfa_key == "Fiş Geçmişi":
    _page_fis_gecmisi(hesap_kodlari)

elif sayfa_key == "Mükellef Yönetimi":
    _page_mukellef_yonetimi()

elif sayfa_key == "KDV Özeti":
    _page_kdv_ozeti(hesap_kodlari)

elif sayfa_key == "Beyanname Takvimi":
    _page_beyanname_takvimi()

elif sayfa_key == "E-Fatura Sorgu":
    _page_efatura_sorgu()

elif sayfa_key == "Ayarlar":
    _page_ayarlar()
