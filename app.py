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
    _page_mukellef_yonetimi, _page_kdv_ozeti, _page_ayarlar
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

st.components.v1.html("""
<script>
if (localStorage.getItem("smmm_auth") === "1" && window.location.search !== "?smmm_auth=1") {
    window.location.search = "?smmm_auth=1";
}
</script>
""", height=0)

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
            log.warning("AUTH_FILE okunamadı", exc_info=True)

    def _sifre_esles(girilen, kayitli):
        import hashlib
        if isinstance(kayitli, str) and kayitli.startswith("sha256:"):
            return hashlib.sha256(girilen.encode("utf-8")).hexdigest() == kayitli[7:]
        return girilen == kayitli

    if pws:
        st.title("SMMM Z Raporu Sistemi")
        st.markdown("Yetkili kullanıcı girişi")
        pwd = st.text_input("Şifre", type="password", placeholder="Şifrenizi girin")
        if st.button("Giriş", type="primary"):
            if any(_sifre_esles(pwd, pw) for pw in pws):
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

if "tema" not in st.session_state:
    st.session_state.tema = "light"

tema_uygula()

for klasor in [GECMIS_KLASORU, FISLER_KLASORU, YEDEK_KLASORU]:
    os.makedirs(klasor, exist_ok=True)

# AUTH_FILE migrate: eski plaintext sifreler sha256:'e cevrilir
def _migrate_auth_file():
    if not os.path.exists(AUTH_FILE):
        return
    try:
        import hashlib
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        pws = data.get("passwords", [])
        if any(isinstance(p, str) and not p.startswith(("sha256:", "plain:")) for p in pws):
            upgraded = []
            for p in pws:
                if isinstance(p, str) and not p.startswith(("sha256:", "plain:")):
                    h = hashlib.sha256(p.encode("utf-8")).hexdigest()
                    upgraded.append(f"sha256:{h}")
                else:
                    upgraded.append(p)
            data["passwords"] = upgraded
            with open(AUTH_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            log.info("AUTH_FILE: plaintext sifreler sha256'e donusturuldu")
    except Exception as e:
        log.warning(f"AUTH_FILE migrate edilemedi: {e}")

_migrate_auth_file()

st.title("📊 SMMM Z Raporu ve Fiş Yönetim Sistemi")
st.caption("Akıllı OCR · LUCA/Logo/Netsis Export · Bilanço & Serbest Meslek")

with st.sidebar:
    if not st.session_state.get("_sidebar_brand_done"):
        st.markdown("""
        <div style="text-align:center;padding:0.5rem 0 1rem 0;">
            <div style="font-size:2.2rem;font-weight:800;letter-spacing:-0.03em;
                        background:linear-gradient(135deg,#0F766E,#14B8A6);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                        background-clip:text;">SMMM</div>
            <div style="font-size:0.75rem;color:#94a3b8;letter-spacing:0.08em;text-transform:uppercase;margin-top:-2px;">Z Raporu Sistemi</div>
        </div>""", unsafe_allow_html=True)
        st.session_state["_sidebar_brand_done"] = True
    """, unsafe_allow_html=True)
    st.divider()
    _sayfa_ikon = {"Dashboard": "📊", "Z Raporu Yükle": "📄", "Fiş Geçmişi": "📋",
                   "Mükellef Yönetimi": "👤", "KDV Özeti": "🧾", "Ayarlar": "⚙️"}
    sayfa = st.radio(
        "Sayfa Seç",
        list(_sayfa_ikon.keys()),
        format_func=lambda x: f"{_sayfa_ikon.get(x, '')} {x}",
        label_visibility="collapsed",
    )

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

elif sayfa_key == "Ayarlar":
    _page_ayarlar()
