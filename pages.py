import os
import io
import re
import glob
import shutil
from datetime import datetime, timedelta
import streamlit as st
from utils import log

from config import (
    HESAP_FILE, GECMIS_KLASORU, MUKELLEF_FILE, SABLON_FILE,
    OGRENILEN_SOZLUK, DUZELTME_SOZLUK, YEDEK_KLASORU, DATA_DIR,
    FISLER_KLASORU, GOT_OCR_API, EMAIL_FILE,
    URUN_KODLARI_FILE
)
from luca import HESAP_PLANLARI
from utils import dosya_oku, dosya_yaz, log
from ocr import (
    ocr_gorsel_isle, parse_z_raporu, ocr_engine, BARCODE_MEVCUT,
    barkod_oku, ogr_alanlari_uygula, duzeltme_ogren, ogrenci_alan_bul,
    ogr_alan_kaydet, got_ocr_api_saglik, turkce_normalize, duzeltme_sozlugu,
    ogrenilen_sozluk
)
from ocr_cache import ocr_gorsel_isle_cached, ocr_cache_istatistik, ocr_cache_temizle
from veritabani import (
    mukellefler, _mukellef_eslestir, gecmis_kaydet, gecmis_listele,
    tum_fisleri_yukle, fis_guncelle, toplu_fis_sil, otomatik_yedekle,
    kdv_ogren, email_gonder
)
from luca import (
    data_to_luca_rows, hesapla_luca_rows, generate_excel,
    generate_excel_cached, generate_basit_usul_excel, generate_mukellef_rapor,
    urun_kodlari_varsayilan, urun_kodlari_yukle, urun_kodlari_kaydet,
    varsayilan_kodlar
)


def _init_text(key, value):
    if key not in st.session_state:
        st.session_state[key] = value


def _init_num(key, value):
    if key not in st.session_state:
        st.session_state[key] = float(value or 0)


def _page_z_raporu_yukle(hesap_kodlari):
    from PIL import Image
    import pandas as pd
    import zipfile
    import io
    st.header("Z Raporu Fotoğraf Yükleme ve OCR")

    urun_kodlari = st.session_state.get("urun_kodlari", [])

    ml = mukellefler()

    if "secili_mukellef_idx" not in st.session_state:
        st.session_state.secili_mukellef_idx = 0

    secili_mukellef = st.session_state.get("secili_mukellef", "")
    if secili_mukellef:
        st.info(f"Mükellef: **{secili_mukellef}** (Sidebar'dan değiştirin)")
    else:
        st.warning("Mükellef seçilmedi. Sidebar'dan mükellef seçin.")

    yukleme_modu = st.radio("Yükleme modu", ["📷 Dosya Seç", "📦 ZIP Yükle"], horizontal=True, key="yukleme_modu")

    uploaded_files = []

    if yukleme_modu == "📷 Dosya Seç":
        uploaded_files = st.file_uploader("Z raporu/fiş seç (JPG/PNG/PDF)", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True, key="dosya_yukle")
    else:
        zip_dosya = st.file_uploader("ZIP dosyası yükle (içinde JPG/PNG/PDF)", type=["zip"], key="zip_yukle")
        if zip_dosya:
            try:
                with zipfile.ZipFile(io.BytesIO(zip_dosya.read())) as zf:
                    dosya_adi_list = [n for n in zf.namelist() if n.lower().endswith(('.jpg', '.jpeg', '.png', '.pdf')) and not n.startswith('__MACOSX')]
                    if not dosya_adi_list:
                        st.error("ZIP içinde uygun görsel/PDF bulunamadı.")
                    else:
                        st.success(f"📦 ZIP'te {len(dosya_adi_list)} dosya bulundu")
                        for da in dosya_adi_list:
                            dosya_icerik = zf.read(da)
                            dosya_adi = os.path.basename(da)
                            uploaded_files.append(type('UploadedFile', (), {'name': dosya_adi, 'read': lambda d=dosya_icerik: d, 'seek': lambda s, *a: None})())
            except zipfile.BadZipFile:
                st.error("Geçersiz ZIP dosyası.")

    if uploaded_files:
        yeni_dosya_sayisi = len(uploaded_files)
        eski_dosya_sayisi = st.session_state.get("son_yuklenen_sayisi", 0)
        if yeni_dosya_sayisi != eski_dosya_sayisi:
            st.session_state.son_yuklenen_sayisi = yeni_dosya_sayisi
        pdf_count = sum(1 for f in uploaded_files if f.name.lower().endswith(".pdf"))
        img_count = len(uploaded_files) - pdf_count
        st.success(f"{img_count} görsel, {pdf_count} PDF yüklendi")
        cols = st.columns(5)
        for i, f in enumerate(uploaded_files):
            with cols[i % 5]:
                if f.name.lower().endswith(".pdf"):
                    st.caption(f"📄 {f.name[:20]}")
                else:
                    try:
                        f.seek(0)
                        img = Image.open(f)
                        st.image(img, caption=f.name[:20], width="stretch")
                        f.seek(0)
                    except Exception:
                        st.caption(f"📄 {f.name[:20]}")

    if BARCODE_MEVCUT and uploaded_files:
        with st.expander("Barkod Okuma", expanded=False):
            st.caption("Yüklenen görsellerde barkod/QR kodu varsa otomatik okunur")
            for f in uploaded_files:
                if not f.name.lower().endswith(".pdf"):
                    f.seek(0)
                    try:
                        img = Image.open(f)
                        barkodlar = barkod_oku(img)
                        if barkodlar:
                            for bd in barkodlar:
                                st.success(f"**{bd['type']}**: {bd['data']}")
                        f.seek(0)
                    except Exception:
                        log.warning("Barkod okuma hatası", exc_info=True)
    elif not BARCODE_MEVCUT and uploaded_files:
        pass

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        run_ocr = st.button("HEPSİNİ OKU (OCR)", type="primary", width="stretch", disabled=not uploaded_files, key="ocr_baslat")
    with col_b2:
        if st.button("Temizle", width="stretch", key="ocr_temizle"):
            for k in ["results", "processed"]:
                st.session_state.pop(k, None)
            st.rerun()

    if run_ocr and uploaded_files:
        if ocr_engine is None:
            st.error("Tesseract OCR yuklu degil! Lutfen Tesseract-OCR kurulumunu kontrol edin.")
            st.stop()
        eski_sonuclar = st.session_state.get("results", [])
        if eski_sonuclar:
            for ek in [k for k in st.session_state if k.startswith("ed_") or k.startswith("iade_")]:
                st.session_state.pop(ek, None)
        import time as _time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        try:
            from pdf2image import convert_from_bytes
            PDF2IMAGE_MEVCUT = True
        except ImportError:
            PDF2IMAGE_MEVCUT = False

        dosya_verileri = []
        for uf in uploaded_files:
            uf.seek(0)
            dosya_verileri.append((uf.name, uf.read()))

        toplam = len(dosya_verileri)
        baslama = _time.time()
        status = st.status(f"OCR baslatildi — {toplam} dosya", expanded=True)
        with status:
            st.write(f"Toplam: {toplam} dosya")
            st.write(f"Paralel is parcacigi: {min(4, toplam)}")
            progress_bar = st.progress(0.0)
            log_alani = st.empty()
            tamamlanan = [0]
            toplam_sure_list = [0.0]
            all_results = [None] * toplam

            def _ocr_duzelt_ve_ogren(ocr_text):
                """Gen 2 ogrenme pipeline: auto-duzeltme + alan duzeltme + geri besleme."""
                from ogrenme_cekirdigi import auto_duzeltme_uygula, alan_duzeltme_uygula
                duzeltilmis, duzeltmeler = auto_duzeltme_uygula(ocr_text)
                parsed = parse_z_raporu(duzeltilmis)
                parsed, _alan_duzeltmeleri = alan_duzeltme_uygula(parsed)
                for d in duzeltmeler:
                    if d.get("uygulandi"):
                        from ogrenme_cekirdigi import duzeltme_kaydet
                        duzeltme_kaydet(d["yanlis"], d["dogru"], alan_adi="", kaynak="otomatik")
                ogr_alanlari_uygula(parsed)
                if not parsed.get("ham_text"):
                    parsed["ham_text"] = ocr_text
                return parsed

            def _tek_ocr(idx, fname, data):
                t0 = _time.time()
                try:
                    if fname.lower().endswith(".pdf"):
                        sonuclar = []
                        from pdf_extract import pdf_text_cikar, pdf_sayfalarini_ayir, pdf_text_yeterli_mi
                        pdf_text, kalite = pdf_text_cikar(data)
                        if pdf_text and pdf_text_yeterli_mi(kalite, esik=60.0):
                            parsed = parse_z_raporu(pdf_text)
                            ogr_alanlari_uygula(parsed)
                            parsed["filename"] = fname
                            parsed["ocr_text"] = pdf_text
                            parsed["mukellef_adi"] = ""
                            parsed["_kaynak"] = f"PDF text (kalite: {kalite:.0f})"
                            return idx, [parsed], _time.time() - t0
                        if not PDF2IMAGE_MEVCUT:
                            return idx, [{"filename": fname, "error": "pdf2image yok", "ocr_text": ""}], _time.time() - t0
                        pages = convert_from_bytes(data, dpi=300)
                        for pi, page in enumerate(pages):
                            ocr_text = ocr_gorsel_isle_cached(page.convert("RGB"))
                            parsed = _ocr_duzelt_ve_ogren(ocr_text)
                            parsed["filename"] = f"{fname} - Syf {pi+1}"
                            parsed["ocr_text"] = ocr_text
                            parsed["mukellef_adi"] = ""
                            parsed["_kaynak"] = "PDF OCR fallback"
                            sonuclar.append(parsed)
                        return idx, sonuclar, _time.time() - t0
                    else:
                        img = Image.open(io.BytesIO(data))
                        ocr_text = ocr_gorsel_isle_cached(img)
                        parsed = _ocr_duzelt_ve_ogren(ocr_text)
                        parsed["filename"] = fname
                        parsed["ocr_text"] = ocr_text
                        parsed["mukellef_adi"] = ""
                        return idx, parsed, _time.time() - t0
                except Exception as e:
                    log.error(f"OCR hatasi {fname}: {e}")
                    return idx, {"filename": fname, "error": str(e), "ocr_text": ""}, _time.time() - t0

            max_workers = min(4, toplam)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(_tek_ocr, i, fname, data): i
                    for i, (fname, data) in enumerate(dosya_verileri)
                }
                for future in as_completed(futures):
                    idx, result, sure_fis = future.result()
                    tamamlanan[0] += 1
                    toplam_sure_list[0] += sure_fis
                    if isinstance(result, list):
                        all_results[idx] = result
                    else:
                        all_results[idx] = result
                    gecen = _time.time() - baslama
                    ort = gecen / max(tamamlanan[0], 1)
                    kal = max(toplam - tamamlanan[0], 0) * ort
                    kstr = f"{int(kal//60)}dk {int(kal%60)}sn" if kal >= 60 else f"{int(kal)}sn"
                    gstr = f"{int(gecen//60)}dk {int(gecen%60)}sn" if gecen >= 60 else f"{gecen:.1f}sn"
                    ort_fis = toplam_sure_list[0] / tamamlanan[0]
                    progress_bar.progress(tamamlanan[0] / toplam)
                    log_alani.markdown(
                        f"**{tamamlanan[0]}/{toplam}** tamamlandi | "
                        f"**{gstr}** gecti | **~{kstr}** kaldi | "
                        f"Ort/dosya: **{ort_fis:.1f}sn** | Son: `{dosya_verileri[idx][0]}` ({sure_fis:.1f}sn)"
                    )

        flat_results = []
        for r in all_results:
            if isinstance(r, list):
                flat_results.extend(r)
            else:
                flat_results.append(r)
        all_results = flat_results

        toplam_sure = _time.time() - baslama
        sure_metni = f"{int(toplam_sure//60)}dk {int(toplam_sure%60)}sn" if toplam_sure >= 60 else f"{toplam_sure:.1f}sn"
        status.update(label=f"OCR tamamlandi! Toplam: {sure_metni} ({toplam} dosya, {max_workers} paralel)", state="complete")

        cache_stats = ocr_cache_istatistik()
        cache_ratio = (cache_stats["hits"] * 100 // max(cache_stats["hits"] + cache_stats["misses"], 1))
        if cache_stats["hits"] > 0 or cache_stats["misses"] > 0:
            st.caption(f"OCR Cache: {cache_stats['hits']} isabet / {cache_stats['misses']} yeni (%{cache_ratio} isabet) — {cache_stats['boyut']}/{cache_stats['limit']} dolu")

        st.session_state.results = all_results
        st.session_state.processed = True

        otomatik_muk = None
        for r in all_results:
            if "firma_adi" in r and r["firma_adi"]:
                idx = _mukellef_eslestir(r["firma_adi"], ml)
                if idx is not None:
                    otomatik_muk = ml[idx]["adi"]
                    st.session_state.secili_mukellef_idx = idx
                    break
        if otomatik_muk:
            for r in all_results:
                if "error" not in r:
                    r["mukellef_adi"] = otomatik_muk

        basarili = sum(1 for r in all_results if "error" not in r)
        hatali = len(all_results) - basarili
        if hatali > 0:
            st.warning(f"{basarili} başarılı, {hatali} hatalı")
        else:
            st.success(f"{len(all_results)} Z raporu okundu. Düzenlemelerinizi yapıp 'Geçmişe Kaydet' butonuna basın.")
        st.rerun()

    if st.session_state.get("processed") and st.session_state.results:
        results = st.session_state.results
        st.divider()
        st.subheader(f"Sonuçlar ({len(results)} Z Raporu)")

        try:
            from ocr_dogrulama import ocr_sonuc_dogrula
            for r in results:
                if "error" not in r and "confidence" not in r:
                    try:
                        _dog = ocr_sonuc_dogrula(r, ham_text=r.get("ocr_text", ""))
                        r["confidence"] = _dog["genel_skor"]
                    except Exception:
                        r["confidence"] = 50.0
        except ImportError:
            log.warning("ocr_dogrulama modulu yuklenemedi, guven skoru atlanacak", exc_info=True)

        siralama = st.selectbox("Sıralama", ["📁 Dosya Adı", "⬆️ Güven Düşükten Yükseğe", "⬇️ Güven Yüksekten Düşüğe"], key="sonuc_siralama")
        if "Güven" in siralama:
            results_sorted = sorted(enumerate(results), key=lambda x: x[1].get("confidence", 50), reverse="Yüksekten" in siralama)
            results = [r for _, r in results_sorted]

        if len(results) > 1:
            tab_labels = []
            for r in results:
                conf = r.get("confidence", 50)
                if conf >= 80:
                    icon = "🟢"
                elif conf >= 50:
                    icon = "🟡"
                else:
                    icon = "🔴"
                tab_labels.append(f"{icon} {r.get('filename','?')[:16]}")
            tab_labels.append("📊 Özet")
            tabs = st.tabs(tab_labels)
        else:
            tabs = [st.container()]

        duzeltilebilir = [(i, r) for i, r in enumerate(results) if "error" not in r]

        if duzeltilebilir and len(results) > 1:
            with tabs[-1]:
                st.markdown("**Toplam Özet**")
                toplam_brut = sum(r.get("brut", 0) for _, r in duzeltilebilir)
                toplam_nakit = sum(r.get("nakit", 0) for _, r in duzeltilebilir)
                toplam_kk = sum(r.get("kredi_karti", 0) for _, r in duzeltilebilir)
                toplam_iade = sum(r.get("iadeler", 0) for _, r in duzeltilebilir)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Toplam Brüt", f"{toplam_brut:,.2f} TL")
                c2.metric("Toplam Nakit", f"{toplam_nakit:,.2f} TL")
                c3.metric("Toplam K.Kartı", f"{toplam_kk:,.2f} TL")
                c4.metric("Toplam İade", f"{toplam_iade:,.2f} TL")

        for tab_idx, tab in enumerate(tabs[:-1] if len(results) > 1 else tabs):
            r = results[tab_idx]
            with tab:
                if "error" in r:
                    st.error(f"❌ {r.get('filename','')}: {r.get('error','')}")
                    continue
                st.markdown(f"**{r.get('filename','')}**")
                try:
                    from ocr_dogrulama import ocr_sonuc_dogrula
                    _dog = ocr_sonuc_dogrula(r, ham_text=r.get("ocr_text", ""))
                    _skor = _dog["genel_skor"]
                    _sorun = _dog["sorunlu_alan_sayisi"]
                    if _skor >= 80:
                        st.success(f"✅ Doğruluk: %{_skor:.0f} ({_sorun} sorun)", icon="🟢")
                    elif _skor >= 50:
                        st.warning(f"⚠️ Doğruluk: %{_skor:.0f} ({_sorun} sorun)", icon="🟡")
                    else:
                        st.error(f"❌ Doğruluk: %{_skor:.0f} ({_sorun} sorun)", icon="🔴")
                except Exception:
                    pass
                c1, c2, c3 = st.columns(3)
                with c1:
                    _init_text(f"ed_tarih_{tab_idx}", r.get("tarih") or "")
                    st.text_input("Tarih", key=f"ed_tarih_{tab_idx}")
                    _init_text(f"ed_firma_{tab_idx}", r.get("firma_adi") or "")
                    st.text_input("Firma", key=f"ed_firma_{tab_idx}")
                    _init_text(f"ed_banka_{tab_idx}", r.get("banka_adi") or "")
                    st.text_input("Banka", key=f"ed_banka_{tab_idx}")
                    _init_text(f"ed_zno_{tab_idx}", r.get("z_no") or "")
                    st.text_input("Z No", key=f"ed_zno_{tab_idx}")
                with c2:
                    _init_num(f"ed_brut_{tab_idx}", float(r.get("brut", 0) or 0))
                    st.number_input("Brüt (TL)", min_value=0.0, step=100.0, key=f"ed_brut_{tab_idx}")
                    _init_num(f"ed_net_{tab_idx}", float(r.get("net_toplam", 0) or 0))
                    st.number_input("Net (TL)", min_value=0.0, step=100.0, key=f"ed_net_{tab_idx}")
                    _init_num(f"ed_nakit_{tab_idx}", float(r.get("nakit", 0) or 0))
                    st.number_input("Nakit (TL)", min_value=0.0, step=100.0, key=f"ed_nakit_{tab_idx}")
                with c3:
                    _init_num(f"ed_kk_{tab_idx}", float(r.get("kredi_karti", 0) or 0))
                    st.number_input("K.Kartı (TL)", min_value=0.0, step=100.0, key=f"ed_kk_{tab_idx}")
                    _init_num(f"ed_yemek_{tab_idx}", float(r.get("yemek_ceki", 0) or 0))
                    st.number_input("Yemek Çeki (TL)", min_value=0.0, step=100.0, key=f"ed_yemek_{tab_idx}")
                    _init_num(f"ed_iade_{tab_idx}", float(r.get("iadeler", 0) or 0))
                    st.number_input("İade (TL)", min_value=0.0, step=100.0, key=f"ed_iade_{tab_idx}")

        if duzeltilebilir:
            with st.expander("📝 Tüm Alanlar — Düzenle & Öğret", expanded=False):
                st.info("Yukarıdaki tab'lardaki alanları düzeltin. 'Kaydet ve Öğret' basınca sistem bir dahaki sefere otomatik düzeltir.")
                if st.button("✅ Kaydet ve Öğret", type="primary", use_container_width=True, key="ed_kaydet"):
                    ogr_sayisi = 0
                    eslesme_ekisik = []
                    degisiklik = []
                    for idx, r in duzeltilebilir:
                        ham = r.get("ham_text", "") or r.get("ocr_text", "")
                        eski_firma = r.get("firma_adi") or ""
                        yeni_firma = st.session_state.get(f"ed_firma_{idx}", "").strip()
                        if yeni_firma and yeni_firma != eski_firma:
                            r["firma_adi"] = yeni_firma
                            ogr_alan_kaydet("firma_adi", yeni_firma)
                            ogr_sayisi += 1
                            degisiklik.append(f"Firma: {eski_firma} → {yeni_firma}")
                            yanlis = ogrenci_alan_bul(ham, "firma_adi", yeni_firma)
                            if yanlis and yanlis.upper() != yeni_firma.upper():
                                duzeltme_ogren(yanlis, yeni_firma)
                            else:
                                eslesme_ekisik.append(("Firma", yeni_firma, yanlis))
                        yeni_tarih = st.session_state.get(f"ed_tarih_{idx}", "").strip()
                        if yeni_tarih and yeni_tarih != (r.get("tarih") or ""):
                            r["tarih"] = yeni_tarih
                            ogr_alan_kaydet("tarih", yeni_tarih)
                            ogr_sayisi += 1
                            degisiklik.append(f"Tarih: {r.get('tarih','')} → {yeni_tarih}")
                            yanlis = ogrenci_alan_bul(ham, "tarih", yeni_tarih)
                            if yanlis and yanlis.upper() != yeni_tarih.upper():
                                duzeltme_ogren(yanlis, yeni_tarih)
                            else:
                                eslesme_ekisik.append(("Tarih", yeni_tarih, yanlis))
                        yeni_banka = st.session_state.get(f"ed_banka_{idx}", "").strip()
                        if yeni_banka and yeni_banka != (r.get("banka_adi") or ""):
                            r["banka_adi"] = yeni_banka
                            ogr_alan_kaydet("banka_adi", yeni_banka)
                            ogr_sayisi += 1
                            degisiklik.append(f"Banka: {r.get('banka_adi','')} → {yeni_banka}")
                            yanlis = ogrenci_alan_bul(ham, "banka_adi", yeni_banka)
                            if yanlis and yanlis.upper() != yeni_banka.upper():
                                duzeltme_ogren(yanlis, yeni_banka)
                            else:
                                eslesme_ekisik.append(("Banka", yeni_banka, yanlis))
                        yeni_zno = st.session_state.get(f"ed_zno_{idx}", "").strip()
                        if yeni_zno and yeni_zno != (r.get("z_no") or ""):
                            r["z_no"] = yeni_zno
                            ogr_alan_kaydet("z_no", yeni_zno)
                            ogr_sayisi += 1
                            degisiklik.append(f"Z No: {r.get('z_no','')} → {yeni_zno}")
                        yeni_brut = st.session_state.get(f"ed_brut_{idx}", 0)
                        if yeni_brut != r.get("brut", 0):
                            degisiklik.append(f"Brüt: {r.get('brut',0):.2f} → {yeni_brut:.2f}")
                        r["brut"] = yeni_brut
                        yeni_net = st.session_state.get(f"ed_net_{idx}", 0)
                        if yeni_net != r.get("net_toplam", 0):
                            degisiklik.append(f"Net: {r.get('net_toplam',0):.2f} → {yeni_net:.2f}")
                        r["net_toplam"] = yeni_net
                        yeni_nakit = st.session_state.get(f"ed_nakit_{idx}", 0)
                        if yeni_nakit != r.get("nakit", 0):
                            degisiklik.append(f"Nakit: {r.get('nakit',0):.2f} → {yeni_nakit:.2f}")
                        r["nakit"] = yeni_nakit
                        yeni_kk = st.session_state.get(f"ed_kk_{idx}", 0)
                        if yeni_kk != r.get("kredi_karti", 0):
                            degisiklik.append(f"K.Kartı: {r.get('kredi_karti',0):.2f} → {yeni_kk:.2f}")
                        r["kredi_karti"] = yeni_kk
                        yeni_yemek = st.session_state.get(f"ed_yemek_{idx}", 0)
                        if yeni_yemek != r.get("yemek_ceki", 0):
                            degisiklik.append(f"Yemek: {r.get('yemek_ceki',0):.2f} → {yeni_yemek:.2f}")
                        r["yemek_ceki"] = yeni_yemek
                        yeni_iade = st.session_state.get(f"ed_iade_{idx}", 0)
                        if yeni_iade != r.get("iadeler", 0):
                            degisiklik.append(f"İade: {r.get('iadeler',0):.2f} → {yeni_iade:.2f}")
                        r["iadeler"] = yeni_iade
                    st.session_state.results = results
                    secili_muk = st.session_state.get("secili_mukellef", "")

                    sozluk_oncesi = len(ogrenilen_sozluk())
                    alan_oncesi = len(ogrenilen_alanlar() if 'ogrenilen_alanlar' in dir() else {})
                    kayit_hatasi = None
                    kayit_sonuc = None
                    try:
                        if not results or not isinstance(results, list):
                            raise ValueError("results boş veya geçersiz - tekrar OCR çalıştırın")
                        kayit_sonuc = gecmis_kaydet(results, hesap_kodlari, secili_muk)
                    except Exception as e:
                        kayit_hatasi = f"{type(e).__name__}: {e}"
                        log.error(f"Kaydet hatasi: {e}")
                        log.error(traceback.format_exc())

                    sozluk_sonra = len(ogrenilen_sozluk())
                    eklenen_kelime = sozluk_sonra - sozluk_oncesi
                    ogr_mesaj_parts = []
                    if ogr_sayisi > 0:
                        ogr_mesaj_parts.append(f"📚 **{ogr_sayisi}** alan öğrenildi (firma/banka/tarih/Z No)")
                    if eklenen_kelime > 0:
                        ogr_mesaj_parts.append(f"🔤 **{eklenen_kelime}** yeni kelime düzeltmesi öğrenildi")
                    if kayit_hatasi:
                        st.session_state.kaydet_bildirim = {
                            "tip": "hata",
                            "mesaj": f"❌ **Kaydetme başarısız!**",
                            "detay": f"Hata: {kayit_hatasi[:200]}",
                            "ogren_sayisi": 0,
                            "eklenen_kelime": 0,
                        }
                    elif kayit_sonuc and kayit_sonuc.get("ogrenme_hatasi"):
                        dosya_adi = os.path.basename(kayit_sonuc.get("dosya_yolu", "?"))
                        st.session_state.kaydet_bildirim = {
                            "tip": "uyari",
                            "mesaj": f"⚠️ **Kaydedildi** (öğrenme kısmi hata)",
                            "detay": f"💾 Dosya: {dosya_adi} | Öğrenme: {kayit_sonuc['ogrenme_hatasi'][:100]}",
                            "ogren_sayisi": ogr_sayisi,
                            "eklenen_kelime": eklenen_kelime,
                        }
                    elif kayit_sonuc and kayit_sonuc.get("dosya_kayit"):
                        dosya_adi = os.path.basename(kayit_sonuc.get("dosya_yolu", "?"))
                        if ogr_mesaj_parts:
                            st.session_state.kaydet_bildirim = {
                                "tip": "basari",
                                "mesaj": " | ".join(ogr_mesaj_parts),
                                "detay": f"💾 Kaydedildi: {dosya_adi} | {len(degisiklik)} alan güncellendi",
                                "ogren_sayisi": ogr_sayisi,
                                "eklenen_kelime": eklenen_kelime,
                            }
                        elif len(degisiklik) > 0:
                            st.session_state.kaydet_bildirim = {
                                "tip": "bilgi",
                                "mesaj": f"💾 **{len(degisiklik)}** alan güncellendi ve kaydedildi.",
                                "detay": f"Dosya: {dosya_adi}",
                                "ogren_sayisi": 0,
                                "eklenen_kelime": 0,
                            }
                        else:
                            st.session_state.kaydet_bildirim = {
                                "tip": "bilgi",
                                "mesaj": f"ℹ️ Değişiklik yok, kayıt yeniden yazıldı.",
                                "detay": f"Dosya: {dosya_adi} | Ayarlar → OCR Öğrenme bölümünden öğrenilen düzeltmelere bakabilirsiniz.",
                                "ogren_sayisi": 0,
                                "eklenen_kelime": 0,
                            }
                    elif ogr_mesaj_parts:
                        st.session_state.kaydet_bildirim = {
                            "tip": "basari",
                            "mesaj": " | ".join(ogr_mesaj_parts),
                            "detay": f"💾 {len(degisiklik)} alan veritabanına kaydedildi.",
                            "ogren_sayisi": ogr_sayisi,
                            "eklenen_kelime": eklenen_kelime,
                        }
                    elif len(degisiklik) > 0:
                        st.session_state.kaydet_bildirim = {
                            "tip": "bilgi",
                            "mesaj": f"💾 {len(degisiklik)} alan güncellendi.",
                            "detay": "",
                            "ogren_sayisi": 0,
                            "eklenen_kelime": 0,
                        }
                    else:
                        st.session_state.kaydet_bildirim = {
                            "tip": "bilgi",
                            "mesaj": "ℹ️ Değişiklik yok, eski değerler korundu.",
                            "detay": "Ayarlar → OCR Öğrenme bölümünden öğrenilen düzeltmelere bakabilirsiniz.",
                            "ogren_sayisi": 0,
                            "eklenen_kelime": 0,
                        }
                    st.rerun()

        _bildirim = st.session_state.pop("kaydet_bildirim", None)
        if _bildirim:
            if _bildirim["tip"] == "basari":
                st.success(_bildirim["mesaj"])
                if _bildirim.get("detay"):
                    st.caption(_bildirim["detay"])
                st.caption("📖 Öğrenilen düzeltmeleri görmek için → **Ayarlar → OCR Öğrenme**")
            elif _bildirim["tip"] == "bilgi":
                st.info(_bildirim["mesaj"])
                if _bildirim.get("detay"):
                    st.caption(_bildirim["detay"])
            elif _bildirim["tip"] == "hata":
                st.error(_bildirim["mesaj"])
                if _bildirim.get("detay"):
                    st.code(_bildirim["detay"])
                st.warning("⚠️ Veri kaydedilemedi! Tekrar deneyin veya sayfayı yenileyin.")
            elif _bildirim["tip"] == "uyari":
                st.warning(_bildirim["mesaj"])
                if _bildirim.get("detay"):
                    st.caption(_bildirim["detay"])
            if _bildirim.get("ogren_sayisi", 0) > 0 or _bildirim.get("eklenen_kelime", 0) > 0:
                st.toast(
                    f"✅ Öğrenildi! ({_bildirim.get('ogren_sayisi', 0)} alan, {_bildirim.get('eklenen_kelime', 0)} kelime)",
                    icon="📚",
                )

        ozet_data = []
        for i, r in enumerate(results):
            if "error" in r:
                ozet_data.append({"#": i+1, "Dosya": r["filename"], "Durum": "HATA", "Tarih": "", "Z No": "", "Firma": "", "Banka": "", "Brüt": 0, "Net": 0, "KK": 0, "Nakit": 0, "İptal": 0})
                continue
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

        iade_eksik = [(i, r) for i, r in enumerate(results) if "error" not in r]
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
                if st.button("İade Tutarlarını Kaydet", type="primary", use_container_width=True, key="iade_kaydet"):
                    for idx, r in iade_eksik:
                        r["iadeler"] = st.session_state.get(f"iade_{idx}", 0)
                    st.toast("İade tutarları kaydedildi!", icon="✅")
                    st.rerun()

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
        otomatik_muk_adi = st.session_state.get("secili_mukellef", "")
        if mod == "Serbest Meslek":
            muk_bilgi = None
            for m in mukellefler():
                if m.get("adi") == otomatik_muk_adi:
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

        st.divider()
        if st.button("Geçmişe Kaydet", type="primary", use_container_width=True, key="gecmis_kaydet_btn"):
            kayit_basarili = True
            try:
                gecmis_kaydet(results, hesap_kodlari, st.session_state.get("secili_mukellef", ""))
            except Exception as e:
                kayit_basarili = False
                log.error(f"Gecmis kaydedilemedi: {e}")
            try:
                kdv_ogren(results, st.session_state.urun_kodlari)
            except Exception as e:
                log.error(f"KDV ogrenme hatası: {e}")
            try:
                basarili = sum(1 for r in results if "error" not in r)
                if basarili > 0:
                    muk_adi = st.session_state.get("secili_mukellef", "Bilinmeyen")
                    toplam_ciro = sum(r.get("net_toplam", 0) or 0 for r in results if "error" not in r)
                    konu = f"SMMM Z Raporu - {muk_adi} - {basarili} Fiş"
                    icerik = f"Mükellef: {muk_adi}\nİşlenen: {basarili} fiş\nToplam Ciro: {toplam_ciro:,.2f} TL"
                    email_gonder(konu, icerik)
            except Exception as e:
                log.error(f"Email bildirim hatası: {e}")
            try:
                otomatik_yedekle()
            except Exception as e:
                log.error(f"Otomatik yedek hatası: {e}")
            if kayit_basarili:
                st.session_state.pop("results", None)
                st.session_state.pop("processed", None)
                st.success("Düzenlenen veriler geçmişe kaydedildi!")
            else:
                st.error("Kayıt sırasında hata oluştu, veriler korundu.")
            st.rerun()

        with st.expander("OCR Ham Metinler"):
            for i, r in enumerate(results):
                if "error" not in r:
                    st.markdown(f"**{i+1}. {r.get('filename','')} — Z No: {r.get('z_no','?')}**")
                    st.text(r.get("ocr_text", ""))
                    st.divider()


def _tarih_esles(fis, yil, ay):
    t = fis.get("tarih", "")
    try:
        d = datetime.strptime(t, "%d.%m.%Y")
        return d.year == yil and d.month == ay
    except (ValueError, TypeError):
        return False


def _filtrele_tarih(fisler, bas, son):
    """Fis listesini tarih araligina gore filtrele."""
    if not bas and not son:
        return fisler
    sonuc = []
    for f in fisler:
        t = f.get("tarih", "")
        try:
            d = datetime.strptime(t, "%d.%m.%Y")
            if bas and d < bas:
                continue
            if son and d > son:
                continue
            sonuc.append(f)
        except (ValueError, TypeError):
            continue
    return sonuc


def _page_dashboard():
    import pandas as pd
    from beyanname_takvimi import yaklasan_beyannameler

    st.header("Genel Bakis")

    tum_fisler = tum_fisleri_yukle()
    kayitlar = gecmis_listele()
    ml = mukellefler()

    kritik_beyannameler = [b for b in yaklasan_beyannameler(datetime.now(), 30) if b["kalan_gun"] <= 7]
    if kritik_beyannameler:
        uyari_sayisi = len(kritik_beyannameler)
        en_yakin = kritik_beyannameler[0]
        if en_yakin["kalan_gun"] < 0:
            st.error(
                f"🔴 **{uyari_sayisi} beyanname kaçırıldı!** En yakın: {en_yakin['ad']} — {en_yakin['tarih']} ({en_yakin['kalan_text']}). "
                f"[Beyanname Takvimi sayfasına git →]"
            )
        elif en_yakin["kalan_gun"] == 0:
            st.error(
                f"🔴 **BUGÜN son gün!** {en_yakin['ad']} ({en_yakin['kod']}). "
                f"[Beyanname Takvimi →]"
            )
        elif en_yakin["kalan_gun"] <= 3:
            st.warning(
                f"⚠️ **{uyari_sayisi} yaklaşan beyanname.** En yakın: {en_yakin['ad']} — {en_yakin['kalan_text']} ({en_yakin['tarih']}). "
                f"[Beyanname Takvimi →]"
            )
        else:
            st.info(
                f"📅 **{uyari_sayisi} beyanname T-7 içinde.** En yakın: {en_yakin['ad']} — {en_yakin['kalan_text']} ({en_yakin['tarih']})."
            )

    if tum_fisler:
        tum_tarihler = []
        for f in tum_fisler:
            t = f.get("tarih", "")
            try:
                tum_tarihler.append(datetime.strptime(t, "%d.%m.%Y"))
            except (ValueError, TypeError):
                continue
        if tum_tarihler:
            min_t = min(tum_tarihler)
            max_t = max(tum_tarihler)
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtre_bas = st.date_input("Baslangic", value=min_t, min_value=min_t, max_value=max_t, key="dash_bas")
            with col_f2:
                filtre_son = st.date_input("Bitis", value=max_t, min_value=min_t, max_value=max_t, key="dash_son")
            filtre_bas_dt = datetime(filtre_bas.year, filtre_bas.month, filtre_bas.day)
            filtre_son_dt = datetime(filtre_son.year, filtre_son.month, filtre_son.day, 23, 59, 59)
            tum_fisler = _filtrele_tarih(tum_fisler, filtre_bas_dt, filtre_son_dt)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Kayit", f"{len(kayitlar)}")
    c2.metric("Toplam Fis", f"{len(tum_fisler)}")
    c3.metric("Aktif Mükellef", f"{len(ml)}")
    toplam_ciro = sum(f.get("net_toplam", 0) or 0 for f in tum_fisler)
    c4.metric("Toplam Ciro", f"{toplam_ciro:,.0f} TL")

    if not tum_fisler:
        st.info("Henuz fis yok. Z Raporu yukleyin.")
        return

    st.divider()

    now = datetime.now()
    ay_isimleri = ["Oca", "Sub", "Mar", "Nis", "May", "Haz", "Tem", "Agu", "Eyl", "Eki", "Kas", "Ara"]

    ay_ciro = {}
    ay_fis_sayisi = {}
    for f in tum_fisler:
        t = f.get("tarih", "")
        try:
            d = datetime.strptime(t, "%d.%m.%Y")
            ay_key = f"{d.year}-{d.month:02d}"
            net = f.get("net_toplam", 0) or 0
            ay_ciro[ay_key] = ay_ciro.get(ay_key, 0) + net
            ay_fis_sayisi[ay_key] = ay_fis_sayisi.get(ay_key, 0) + 1
        except (ValueError, TypeError):
            continue

    if ay_ciro:
        st.subheader("Aylik Ciro Trendi")
        sorted_aylar = sorted(ay_ciro.keys())
        df_ay = pd.DataFrame({
            "Ay": [f"{ay_isimleri[int(a.split('-')[1])-1]} {a.split('-')[0]}" for a in sorted_aylar],
            "Ciro (TL)": [ay_ciro[a] for a in sorted_aylar],
            "Fis Sayisi": [ay_fis_sayisi.get(a, 0) for a in sorted_aylar],
        })
        st.bar_chart(df_ay.set_index("Ay")[["Ciro (TL)"]], use_container_width=True)

    col_banka, col_mukellef = st.columns(2)
    with col_banka:
        st.subheader("Banka Bazli Ciro")
        banka_ciro = {}
        for f in tum_fisler:
            b = f.get("banka_adi", "") or "Belirsiz/Nakit"
            banka_ciro[b] = banka_ciro.get(b, 0) + (f.get("net_toplam", 0) or 0)
        if banka_ciro:
            df_b = pd.DataFrame([{"Banka": k, "Ciro": v} for k, v in sorted(banka_ciro.items(), key=lambda x: -x[1])])
            st.bar_chart(df_b.set_index("Banka"), use_container_width=True)

    with col_mukellef:
        st.subheader("Mükellef Bazlı Ciro")
        musteri_ciro = {}
        for f in tum_fisler:
            m = f.get("mukellef", "") or f.get("mukellef_adi", "") or "Bilinmeyen"
            musteri_ciro[m] = musteri_ciro.get(m, 0) + (f.get("net_toplam", 0) or 0)
        if musteri_ciro:
            df_m = pd.DataFrame([{"Mükellef": k, "Ciro": v} for k, v in sorted(musteri_ciro.items(), key=lambda x: -x[1])])
            st.bar_chart(df_m.set_index("Mükellef"), use_container_width=True)

    st.divider()
    st.subheader("Karsilastirma")
    bu_yil = now.year
    gecen_ay = now.month - 1 if now.month > 1 else 12
    gecen_ay_yil = bu_yil if now.month > 1 else bu_yil - 1
    bu_yil_ciro = 0
    gecen_yil_ciro = 0
    bu_ay_ciro = 0
    gecen_ay_ciro = 0
    for f in tum_fisler:
        t = f.get("tarih", "")
        try:
            d = datetime.strptime(t, "%d.%m.%Y")
            net = f.get("net_toplam", 0) or 0
            if d.year == bu_yil:
                bu_yil_ciro += net
            if d.year == bu_yil - 1:
                gecen_yil_ciro += net
            if d.year == bu_yil and d.month == now.month:
                bu_ay_ciro += net
            if d.year == gecen_ay_yil and d.month == gecen_ay:
                gecen_ay_ciro += net
        except (ValueError, TypeError):
            continue
    ay_fark = bu_ay_ciro - gecen_ay_ciro
    yil_fark = bu_yil_ciro - gecen_yil_ciro
    ay_yuzde = (ay_fark / gecen_ay_ciro * 100) if gecen_ay_ciro > 0 else 0
    yil_yuzde = (yil_fark / gecen_yil_ciro * 100) if gecen_yil_ciro > 0 else 0
    comp1, comp2 = st.columns(2)
    comp1.metric(f"Bu Ay ({ay_isimleri[now.month-1]})", f"{bu_ay_ciro:,.0f} TL", f"{ay_fark:+,.0f} TL ({ay_yuzde:+.1f}%)")
    comp2.metric(f"Bu Yil ({bu_yil})", f"{bu_yil_ciro:,.0f} TL", f"{yil_fark:+,.0f} TL ({yil_yuzde:+.1f}%)")

    fis_sayisi_ay = len([f for f in tum_fisler if _tarih_esles(f, bu_yil, now.month)])
    fis_sayisi_gecen = len([f for f in tum_fisler if _tarih_esles(f, gecen_ay_yil, gecen_ay)])
    st.caption(f"Bu ay {fis_sayisi_ay} fis, gecen ay {fis_sayisi_gecen} fis")

    st.divider()
    st.subheader("OCR Öğrenme Sistemi")
    try:
        from ogrenme_cekirdigi import istatistik_raporu, duzeltme_listesi, duzeltme_reddet
        rapor = istatistik_raporu()
        if rapor["toplam_kayit"] > 0:
            col_o1, col_o2, col_o3 = st.columns(3)
            col_o1.metric("Öğrenilen Düzeltme", rapor["toplam_kayit"])
            col_o2.metric("Yüksek Güvenli", rapor["yuksek_guven"])
            col_o3.metric("Toplam Uygulama", rapor["istatistik"]["auto_uygulanan"])
            st.caption(f"Sistem {rapor['toplam_duzeltme_sayisi']} düzeltme deneyimiyle {rapor['yuksek_guven']} yüksek güvenli kural öğrendi. "
                       f"Reddedilen: {rapor['istatistik'].get('reddedilen', 0)}")

            with st.expander("Öğrenilen Düzeltmeleri Yönet", expanded=False):
                liste = duzeltme_listesi(siralama="guven", limit=50)
                for item in liste:
                    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                    c1.caption(f"`{item['key']}`")
                    c2.success(f"→ {item['dogru']}")
                    c3.metric("Güven", f"%{item['guven']*100:.0f}")
                    if item["guven"] < 0.75 and st.button("Reddet", key=f"red_{item['key']}"):
                        duzeltme_reddet(item["key"])
                        st.rerun()
        else:
            st.caption("Henüz öğrenme verisi yok. Fiş düzelttikçe sistem otomatik öğrenir.")
    except ImportError:
        pass


def _page_fis_gecmisi(hesap_kodlari):
    import pandas as pd
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
            with st.expander("Toplu İşlem", expanded=False):
                col_del1, col_del2 = st.columns([3, 1])
                with col_del1:
                    secim = st.multiselect("Silmek istediklerinizi seçin",
                        options=filtered,
                        format_func=lambda x: f"{x.get('tarih','')} | {x.get('z_no','')} | {x.get('firma_adi', x.get('mukellef',''))} | ₺{x.get('net_toplam', 0):,.2f}")
                with col_del2:
                    st.write("")
                    st.write("")
                    if secim and st.button("Seçilenleri Sil", type="primary", key="toplu_sil"):
                        silinen = toplu_fis_sil(secim)
                        if silinen > 0:
                            st.success(f"{silinen} fiş silindi!")
                            st.rerun()
                        else:
                            st.error("Hiçbir fiş silinemedi.")

            with st.expander("Fiş Düzenle", expanded=False):
                secim_duzelt = st.selectbox("Düzenlenecek fişi seçin", filtered,
                    format_func=lambda x: f"{x.get('tarih','')} | {x.get('z_no','')} | {x.get('firma_adi', x.get('mukellef',''))} | ₺{x.get('net_toplam', 0):,.2f}",
                    key="duzelt_secim")
                if secim_duzelt:
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        yeni_tarih = st.text_input("Tarih", value=secim_duzelt.get("tarih", ""), key="ed_tarih_fis")
                        yeni_brut = st.number_input("Brüt Tutar", value=float(secim_duzelt.get("brut", 0) or 0), step=100.0, key="ed_brut_fis")
                        yeni_nakit = st.number_input("Nakit", value=float(secim_duzelt.get("nakit", 0) or 0), step=100.0, key="ed_nakit_fis")
                    with col_d2:
                        yeni_net = st.number_input("Net Tutar", value=float(secim_duzelt.get("net_toplam", 0) or 0), step=100.0, key="ed_net_fis")
                        yeni_kk = st.number_input("Kredi Kartı", value=float(secim_duzelt.get("kredi_karti", 0) or 0), step=100.0, key="ed_kk_fis")
                        yeni_iade = st.number_input("İade", value=float(secim_duzelt.get("iadeler", 0) or 0), step=100.0, key="ed_iade_fis")
                    if st.button("Değişiklikleri Kaydet", type="primary", key="kaydet_duzelt"):
                        yeni_veriler = {
                            "tarih": yeni_tarih,
                            "brut": yeni_brut,
                            "net_toplam": yeni_net,
                            "nakit": yeni_nakit,
                            "kredi_karti": yeni_kk,
                            "iadeler": yeni_iade,
                        }
                        if fis_guncelle(secim_duzelt, yeni_veriler):
                            ogrenme_mesajlari = []
                            for alan, eski, yeni in [
                                ("tarih", secim_duzelt.get("tarih", ""), yeni_tarih),
                                ("brut", str(secim_duzelt.get("brut", 0)), str(yeni_brut)),
                                ("net_toplam", str(secim_duzelt.get("net_toplam", 0)), str(yeni_net)),
                                ("nakit", str(secim_duzelt.get("nakit", 0)), str(yeni_nakit)),
                                ("kredi_karti", str(secim_duzelt.get("kredi_karti", 0)), str(yeni_kk)),
                                ("iadeler", str(secim_duzelt.get("iadeler", 0)), str(yeni_iade)),
                            ]:
                                if str(eski) != str(yeni) and eski and yeni:
                                    from ogrenme_cekirdigi import duzeltme_kaydet, alan_duzeltme_kaydet
                                    ogr_metin = ogrenci_alan_bul(secim_duzelt.get("ocr_text", ""), alan, str(yeni))
                                    if ogr_metin:
                                        duzeltme_kaydet(ogr_metin, str(yeni), alan_adi=alan, kaynak="manuel")
                                        alan_duzeltme_kaydet(alan, str(eski), str(yeni), kaynak="manuel")
                                        ogrenme_mesajlari.append(f"{alan}: '{ogr_metin}' → '{yeni}'")
                            if ogrenme_mesajlari:
                                st.success(f"Fiş güncellendi ve {len(ogrenme_mesajlari)} düzeltme öğrenildi!")
                            else:
                                st.success("Fiş güncellendi!")
                            st.rerun()

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
                    if m.get("adi") == st.session_state.get("secili_mukellef", ""):
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

            if filtre_mukellef != "Tümü":
                rapor_html = generate_mukellef_rapor(filtered, filtre_mukellef)
                st.download_button("PDF Rapor İndir (HTML)", rapor_html,
                    f"{filtre_mukellef}_rapor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    "text/html", width="stretch",
                    help="HTML dosyasını tarayıcıda açıp Ctrl+P ile PDF olarak kaydedin")


def _page_mukellef_yonetimi():
    st.header("Mükellef Yönetimi")

    ml = mukellefler()

    with st.expander("Yeni Mükellef Ekle", expanded=not ml):
        with st.form("mukellef_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                adi = st.text_input("Mükellef Adı", placeholder="Örn: Ahmet Mağazacılık Ltd.")
                vergi_no = st.text_input("Vergi No", placeholder="1234567890")
                mod = st.selectbox("Muhasebe Türü", ["Bilanço", "Serbest Meslek"])
            with col_b:
                vd = st.text_input("Vergi Dairesi", placeholder="Örn: Kartal VD")
                telefon = st.text_input("Telefon", placeholder="0532 xxx xx xx")
            kisa_adi = st.text_input("Kısa Ad (Opsiyonel)", placeholder="OCR eşleştirmesi için")
            notlar = st.text_area("Notlar", placeholder="Ek bilgiler...")
            submitted = st.form_submit_button("Ekle", type="primary")
            if submitted and adi:
                ml.append({
                    "adi": adi, "vergi_no": vergi_no, "vd": vd,
                    "telefon": telefon, "notlar": notlar, "mod": mod,
                    "kisa_adi": kisa_adi,
                    "olusturma": datetime.now().strftime("%d.%m.%Y")
                })
                dosya_yaz(MUKELLEF_FILE, ml)
                st.success(f"{adi} eklendi!")
                st.rerun()

    if ml:
        st.divider()
        bilanco = [m for m in ml if m.get("mod", "Bilanço") == "Bilanço"]
        sm = [m for m in ml if m.get("mod", "Serbest Meslek") == "Serbest Meslek"]
        st.subheader(f"Kayıtlı Mükellefler ({len(ml)}) — {len(bilanco)} Bilanço, {len(sm)} Serbest Meslek")

        filtre_mod = st.selectbox("Göster", ["Tümü", "Bilanço", "Serbest Meslek"], key="muk_filtre")
        gosterim = ml if filtre_mod == "Tümü" else [m for m in ml if m.get("mod", "Serbest Meslek") == filtre_mod]

        for i, m in enumerate(gosterim):
            mod_etiket = m.get("mod", "?")
            with st.expander(f"{m['adi']} — {m.get('vergi_no', '?')} [{mod_etiket}]"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Vergi Dairesi:** {m.get('vd', '?')}")
                c2.write(f"**Telefon:** {m.get('telefon', '?')}")
                c3.write(f"**Kayıt:** {m.get('olusturma', '?')}")
                if m.get("kisa_adi"):
                    st.write(f"**Kısa Ad:** {m['kisa_adi']}")
                if m.get("notlar"):
                    st.write(f"Not: {m['notlar']}")

                orijinal_idx = ml.index(m)
                if st.button("Sil", key=f"sil_{orijinal_idx}", width="stretch"):
                    ml.pop(orijinal_idx)
                    dosya_yaz(MUKELLEF_FILE, ml)
                    st.rerun()
    else:
        st.info("Henüz mükellef eklenmemiş.")


def _page_kdv_ozeti(hesap_kodlari):
    st.header("Dönemsel KDV Özeti")
    urun_kodlari = st.session_state.get("urun_kodlari", [])

    tum_fisler = tum_fisleri_yukle()
    if not tum_fisler:
        st.info("Henüz fiş yok.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            ml = mukellefler()
            filtre_muk = st.selectbox("Mükellef", ["Tümü"] + [m["adi"] for m in ml])
        with col2:
            ay = st.selectbox("Ay", range(1, 13), index=datetime.now().month - 1)
        with col3:
            yil = st.selectbox("Yıl", range(datetime.now().year, datetime.now().year - 3, -1))

        ay_fisler = []
        for f in tum_fisler:
            try:
                t = datetime.strptime(f.get("tarih", ""), "%d.%m.%Y")
                if t.month == ay and t.year == yil:
                    if filtre_muk != "Tümü":
                        m = f.get("mukellef", "") or f.get("mukellef_adi", "")
                        if m != filtre_muk:
                            continue
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
                    if m.get("adi") == st.session_state.get("secili_mukellef", ""):
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

            if kdv_toplamlari:
                kdv_satirlar = ""
                toplam_matrah = 0
                toplam_kdv_tutari = 0
                for oran in sorted(kdv_toplamlari.keys()):
                    k = kdv_toplamlari[oran]
                    toplam_matrah += k['matrah']
                    toplam_kdv_tutari += k['kdv']
                    kdv_satirlar += (
                        f"<tr><td>%{oran}</td>"
                        f"<td style='text-align:right'>{k['brut']:,.2f}</td>"
                        f"<td style='text-align:right'>{k['matrah']:,.2f}</td>"
                        f"<td style='text-align:right'>{k['kdv']:,.2f}</td></tr>"
                    )
                muk_baslik = filtre_muk if filtre_muk != "Tümü" else "Tüm Mükellefler"
                kdv_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>KDV Beyanname Özeti - {ay:02d}/{yil}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; }}
h1 {{ text-align: center; color: #1a5276; }}
.meta {{ text-align: center; color: #666; }}
table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; }}
th {{ background: #1a5276; color: white; }}
.toplam {{ background: #e8f6f3; font-weight: bold; }}
@media print {{ body {{ margin: 10mm; }} }}
</style></head><body>
<h1>KDV Beyanname Özeti</h1>
<p class="meta">{muk_baslik} | {ay:02d}/{yil} | {len(ay_fisler)} Fiş</p>
<table>
<tr><th>KDV Oranı</th><th>Brüt Tutar</th><th>Matrah</th><th>KDV Tutarı</th></tr>
{kdv_satirlar}
<tr class="toplam"><td>TOPLAM</td><td style="text-align:right">{toplam_ciro:,.2f}</td>
<td style="text-align:right">{toplam_matrah:,.2f}</td>
<td style="text-align:right">{toplam_kdv_tutari:,.2f}</td></tr>
</table>
<h3>Ödeme Türüne Göre</h3>
<table>
<tr><th>Nakit</th><th>Kredi Kartı</th><th>İade</th><th>Net Toplam</th></tr>
<tr><td>{toplam_nakit:,.2f}</td><td>{toplam_kk:,.2f}</td><td>{toplam_iptal:,.2f}</td><td>{toplam_ciro:,.2f}</td></tr>
</table>
<p style="text-align:center;color:#999;margin-top:30px">SMMM Z Raporu ve Fiş Yönetim Sistemi</p>
</body></html>"""
                st.download_button(f"KDV Beyanname Raporu İndir ({ay:02d}/{yil})", kdv_html.encode("utf-8"),
                    f"kdv_beyanname_{yil}_{ay:02d}.html", "text/html", width="stretch",
                    help="HTML dosyasını tarayıcıda açıp Ctrl+P ile PDF olarak kaydedin")

                try:
                    from fpdf import FPDF
                    class KDV_PDF(FPDF):
                        def header(self):
                            self.set_font('Helvetica', 'B', 14)
                            self.cell(0, 10, 'KDV Beyanname Ozeti', ln=True, align='C')
                            self.set_font('Helvetica', '', 10)
                            self.cell(0, 6, f'{muk_baslik} | {ay:02d}/{yil} | {len(ay_fisler)} Fis', ln=True, align='C')
                            self.ln(4)
                        def footer(self):
                            self.set_y(-15)
                            self.set_font('Helvetica', 'I', 8)
                            self.cell(0, 10, f'SMMM Z Raporu Sistemi | Sayfa {self.page_no()}/{{nb}}', align='C')

                    pdf = KDV_PDF()
                    pdf.alias_nb_pages()
                    pdf.add_page()
                    pdf.set_font('Helvetica', 'B', 11)
                    pdf.cell(0, 8, 'KDV Dokumu', ln=True)
                    pdf.set_font('Helvetica', 'B', 9)
                    pdf.set_fill_color(26, 82, 118)
                    pdf.set_text_color(255, 255, 255)
                    pdf.cell(40, 7, 'KDV Orani', border=1, fill=True, align='C')
                    pdf.cell(45, 7, 'Brut Tutar', border=1, fill=True, align='C')
                    pdf.cell(45, 7, 'Matrah', border=1, fill=True, align='C')
                    pdf.cell(45, 7, 'KDV Tutari', border=1, fill=True, align='C')
                    pdf.ln()
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font('Helvetica', '', 9)
                    genel_kdv_pdf = 0
                    for oran in sorted(kdv_toplamlari.keys()):
                        k = kdv_toplamlari[oran]
                        pdf.cell(40, 6, f'%{oran}', border=1, align='C')
                        pdf.cell(45, 6, f'{k["brut"]:,.2f}', border=1, align='R')
                        pdf.cell(45, 6, f'{k["matrah"]:,.2f}', border=1, align='R')
                        pdf.cell(45, 6, f'{k["kdv"]:,.2f}', border=1, align='R')
                        pdf.ln()
                        genel_kdv_pdf += k['kdv']
                    pdf.set_font('Helvetica', 'B', 9)
                    pdf.set_fill_color(232, 246, 243)
                    pdf.cell(40, 7, 'TOPLAM', border=1, fill=True, align='C')
                    pdf.cell(45, 7, f'{toplam_ciro:,.2f}', border=1, fill=True, align='R')
                    pdf.cell(45, 7, f'{toplam_matrah:,.2f}', border=1, fill=True, align='R')
                    pdf.cell(45, 7, f'{genel_kdv_pdf:,.2f}', border=1, fill=True, align='R')
                    pdf.ln(12)
                    pdf.set_font('Helvetica', 'B', 11)
                    pdf.cell(0, 8, 'Odeme Turlerine Gore', ln=True)
                    pdf.set_font('Helvetica', 'B', 9)
                    pdf.set_fill_color(26, 82, 118)
                    pdf.set_text_color(255, 255, 255)
                    pdf.cell(45, 7, 'Nakit', border=1, fill=True, align='C')
                    pdf.cell(45, 7, 'Kredi Karti', border=1, fill=True, align='C')
                    pdf.cell(45, 7, 'Iade', border=1, fill=True, align='C')
                    pdf.cell(45, 7, 'Net Toplam', border=1, fill=True, align='C')
                    pdf.ln()
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font('Helvetica', '', 9)
                    pdf.cell(45, 6, f'{toplam_nakit:,.2f}', border=1, align='R')
                    pdf.cell(45, 6, f'{toplam_kk:,.2f}', border=1, align='R')
                    pdf.cell(45, 6, f'{toplam_iptal:,.2f}', border=1, align='R')
                    pdf.cell(45, 6, f'{toplam_ciro:,.2f}', border=1, align='R')
                    pdf.ln(15)
                    pdf.set_font('Helvetica', 'I', 8)
                    pdf.cell(0, 5, 'SMMM Z Raporu ve Fis Yonetim Sistemi', ln=True, align='C')
                    pdf_bytes = bytes(pdf.output())
                    st.download_button(f"KDV Beyanname PDF Indir ({ay:02d}/{yil})", pdf_bytes,
                        f"kdv_beyanname_{yil}_{ay:02d}.pdf", "application/pdf", width="stretch")
                except ImportError:
                    st.caption("PDF cikisi icin fpdf2 kurun: pip install fpdf2")
                except Exception as e:
                    st.warning(f"PDF olusturulamadi: {e}")


def _page_ayarlar():
    st.header("Ayarlar")

    _cu = st.session_state.get("current_user", {})
    if _cu.get("role") == "admin":
        _kullanici_yonetimi_paneli()

    st.subheader("Yedekleme")
    col_y1, col_y2 = st.columns(2)
    with col_y1:
        if st.button("Yedek Oluştur", width="stretch", type="primary", key="yedek_olustur"):
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
            if st.button("Geri Yükle", width="stretch", key="geri_yukle"):
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
    st.subheader("Bulut Yedekleme (ZIP İndir)")
    st.caption("Tüm verilerinizi ZIP olarak indirip Google Drive, OneDrive veya Dropbox'a yükleyebilirsiniz.")
    if st.button("ZIP Yedek Oluştur ve İndir", type="primary", key="zip_yedek"):
        import zipfile
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fp in [HESAP_FILE, MUKELLEF_FILE, URUN_KODLARI_FILE]:
                if os.path.exists(fp):
                    zf.write(fp, os.path.basename(fp))
            for fp in glob.glob(os.path.join(GECMIS_KLASORU, "*.json")):
                zf.write(fp, f"gecmis/{os.path.basename(fp)}")
            for fp in glob.glob(os.path.join(YEDEK_KLASORU, "yedek_*", "*.json")):
                zf.write(fp, f"yedekler/{os.path.basename(fp)}")
        zip_buffer.seek(0)
        st.download_button("ZIP Dosyasını İndir", zip_buffer,
            f"yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            "application/zip", type="primary", key="zip_indir")

    st.divider()
    st.subheader("E-posta Bildirimi")
    email_config = dosya_oku(EMAIL_FILE, {})
    with st.form("email_form"):
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            smtp_server = st.text_input("SMTP Sunucu", value=email_config.get("smtp_server", ""), placeholder="smtp.gmail.com")
            smtp_port = st.number_input("Port", value=email_config.get("port", 587), min_value=1, max_value=65535)
            gonderen = st.text_input("Gönderen E-posta", value=email_config.get("gonderen", ""), placeholder="ornek@gmail.com")
        with col_e2:
            sifre = st.text_input("Uygulama Şifresi", value=email_config.get("sifre", ""), type="password", placeholder="Google Uygulama Şifresi")
            alici = st.text_input("Alıcı E-posta", value=email_config.get("alici", ""), placeholder="Alıcı (boşsa gönderene gider)")
        if st.form_submit_button("E-posta Ayarlarını Kaydet"):
            yeni_config = {"smtp_server": smtp_server, "port": smtp_port, "gonderen": gonderen, "sifre": sifre, "alici": alici or gonderen}
            dosya_yaz(EMAIL_FILE, yeni_config)
            st.success("E-posta ayarları kaydedildi!")
    if email_config.get("gonderen"):
        if st.button("Test E-postası Gönder", key="test_email"):
            if email_gonder("SMMM Z Raporu - Test", "Bu bir test e-postasıdır. E-posta bildirimi çalışıyor!"):
                st.success("Test e-postası gönderildi!")
            else:
                st.error("E-posta gönderilemedi. Ayarları kontrol edin.")

    st.divider()
    st.subheader("Hesap Planı Seçimi")
    mevcut_plan = st.session_state.get("hesap_plan_secenek", "LUCA")
    yeni_plan = st.selectbox("Muhasebe Programı", ["LUCA", "Logo", "Netsis"],
        index=["LUCA", "Logo", "Netsis"].index(mevcut_plan))
    if yeni_plan != mevcut_plan:
        st.session_state.hesap_plan_secenek = yeni_plan
        yeni_kodlar = HESAP_PLANLARI[yeni_plan].copy()
        dosya_yaz(HESAP_FILE, yeni_kodlar)
        st.session_state.hesap_kodlari = yeni_kodlar
        st.success(f"{yeni_plan} hesap planı yüklendi!")
        st.rerun()
    st.info(f"Aktif hesap planı: **{mevcut_plan}**")
    st.json(st.session_state.get("hesap_kodlari", {}))

    st.divider()
    st.subheader("OCR Düzeltme Sözlüğü")
    st.caption("OCR'ın yanlış okuduğu kelimeleri buradan yönetebilirsiniz. Sistem kullanıcı düzeltmelerinden otomatik öğrenir.")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        sozluk = duzeltme_sozlugu()
        ogrenilen = ogrenilen_sozluk()
        st.info(f"Ana sözlük: **{len(sozluk)}** kelime | Öğrenilen: **{len(ogrenilen)}** kelime")
    with col_s2:
        if ogrenilen:
            if st.button("Öğrenilenleri Temizle", type="secondary", key="ogrenilen_temizle"):
                dosya_yaz(OGRENILEN_SOZLUK, {})
                st.success("Öğrenilen düzeltmeler temizlendi!")
                st.rerun()
        if st.button("Ana Sözlüğü Sıfırla", type="secondary", key="ana_sozluk_sifirla"):
            if os.path.exists(DUZELTME_SOZLUK):
                os.remove(DUZELTME_SOZLUK)
            st.success("Ana sözlük sıfırlandı!")
            st.rerun()
    if ogrenilen:
        st.caption("Öğrenilen Düzeltmeler (OCR'daki hatalı → Doğru):")
        ogrenilen_liste = sorted(ogrenilen.items(), key=lambda x: x[0])
        for i in range(0, len(ogrenilen_liste), 5):
            cols = st.columns(5)
            for j in range(5):
                if i + j < len(ogrenilen_liste):
                    yanlis, dogru = ogrenilen_liste[i + j]
                    cols[j].caption(f"`{yanlis[:15]}` → `{dogru[:15]}`")
    else:
        st.caption("Henüz öğrenilmiş düzeltme yok. Fiş düzelttikçe otomatik öğrenilir.")

    st.divider()
    st.subheader("İstatistiksel Öğrenme Motoru")
    st.caption("Yeni nesil öğrenme sistemi - her düzeltme sayılır, güven puanı hesaplanır.")
    try:
        from ogrenme_cekirdigi import istatistik_raporu, gecmis_temizle, ogrenme_db_yukle
        rapor = istatistik_raporu()
        col_o1, col_o2, col_o3, col_o4 = st.columns(4)
        with col_o1:
            st.metric("Toplam Kayıt", rapor["toplam_kayit"])
        with col_o2:
            st.metric("Yüksek Güven", rapor["yuksek_guven"])
        with col_o3:
            st.metric("Düşük Güven", rapor["dusuk_guven"])
        with col_o4:
            st.metric("Toplam Düzeltme", rapor["toplam_duzeltme_sayisi"])
        if rapor["alan_bazli_kayit"]:
            st.caption("Alan bazlı düzeltme dağılımı:")
            for alan, sayi in rapor["alan_bazli_kayit"].items():
                st.caption(f"  • {alan}: {sayi} kayıt")
        if st.button("Eski Kayıtları Temizle (365+ gün)", type="secondary", key="ogrenme_temizle"):
            silinen = gecmis_temizle(365)
            if silinen > 0:
                st.success(f"{silinen} eski/düşük güvenli kayıt temizlendi!")
                st.rerun()
            else:
                st.info("Temizlenecek kayıt bulunamadı.")
    except ImportError:
        st.caption("İstatistiksel öğrenme motoru yüklenemedi.")

    st.divider()
    st.subheader("Tehlikeli İşlemler")
    if "sil_onay" not in st.session_state:
        st.session_state.sil_onay = False
    if "fis_sil_onay" not in st.session_state:
        st.session_state.fis_sil_onay = False

    if not st.session_state.fis_sil_onay:
        if st.button("TÜM FİŞLERİ SİL", type="secondary", key="tum_fisleri_sil"):
            st.session_state.fis_sil_onay = True
            st.rerun()
    else:
        st.warning("Tüm fişler silinecek! Mükellefler ve ayarlar kalacak.")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if st.button("EMİNİM, FİŞLERİ SİL!", type="primary", width="stretch", key="fis_sil_onayla"):
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
            if st.button("İptal", type="secondary", width="stretch", key="fis_sil_iptal"):
                st.session_state.fis_sil_onay = False
                st.rerun()

    if not st.session_state.sil_onay:
        if st.button("TÜM VERİLERİ SİL", type="secondary", key="tum_verileri_sil"):
            st.session_state.sil_onay = True
            st.rerun()
    else:
        st.warning("Tüm veriler silinecek! Bu işlem geri alınamaz.")
        col_onay, col_iptal = st.columns(2)
        with col_onay:
            if st.button("EMİNİM, SİL!", type="primary", width="stretch", key="veri_sil_onayla"):
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
            if st.button("İptal", type="secondary", width="stretch", key="veri_sil_iptal"):
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


def _page_beyanname_takvimi():
    """Beyanname takvimi + email hatirlatici."""
    import pandas as pd
    from beyanname_takvimi import yaklasan_beyannameler, beyanname_tarihi_hesapla, BEYANNAMELER, email_icerik_olustur

    st.header("Beyanname Takvimi")
    st.caption("KDV, Muhtasar, BA-BS, Geçici Vergi, Gelir/Kurumlar Vergisi tarihleri")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.metric("Bugün", datetime.now().strftime("%d.%m.%Y"))
    with col_f2:
        yaklasan_30 = yaklasan_beyannameler(datetime.now(), 30)
        kritik_sayisi = len([b for b in yaklasan_30 if b["kalan_gun"] <= 3])
        if kritik_sayisi > 0:
            st.metric("⚠️ Kritik (≤3 gün)", f"{kritik_sayisi} beyanname")
        else:
            st.metric("Yaklaşan (30 gün)", f"{len(yaklasan_30)} beyanname")

    st.divider()

    tab_takvim, tab_email = st.tabs(["📅 Takvim", "📧 Email Bildirim"])

    with tab_takvim:
        yaklasan = yaklasan_beyannameler(datetime.now(), 60)

        st.subheader("Yaklaşan Beyannameler (60 gün)")
        if not yaklasan:
            st.info("Yaklaşan 60 gün içinde beyanname yok.")
        else:
            cols = st.columns(min(len(yaklasan), 3))
            for i, b in enumerate(yaklasan):
                with cols[i % 3]:
                    with st.container():
                        if b["kalan_gun"] < 0:
                            st.error(f"**{b['ad']}**")
                        elif b["kalan_gun"] <= 3:
                            st.warning(f"**{b['ad']}**")
                        else:
                            st.info(f"**{b['ad']}**")
                        st.write(f"📅 {b['tarih']}")
                        st.write(b["kalan_text"])
                        st.caption(b["aciklama"])

        st.divider()
        st.subheader("Tüm Beyannameler")
        tum_veri = []
        for kod, info in BEYANNAMELER.items():
            tarih = beyanname_tarihi_hesapla(kod, datetime.now())
            tarih_sonraki = beyanname_tarihi_hesapla(kod, datetime.now() + timedelta(days=120))
            tum_veri.append({
                "Beyanname": info["ad"],
                "Kod": kod,
                "Dönem": info["donem"].capitalize(),
                "Son Gün": tarih.strftime("%d.%m.%Y") if tarih else "-",
                "Sonraki Dönem": tarih_sonraki.strftime("%d.%m.%Y") if tarih_sonraki else "-",
                "Açıklama": info["aciklama"],
            })
        df = pd.DataFrame(tum_veri)
        st.dataframe(df, width="stretch", hide_index=True)

    with tab_email:
        st.subheader("Email Bildirim Ayarları")
        email_config = dosya_oku(EMAIL_FILE, {})

        with st.form("email_ayarlar_form", clear_on_submit=False):
            smtp_server = st.text_input("SMTP Sunucu", value=email_config.get("smtp_server", "smtp.gmail.com"), key="smtp_server")
            smtp_port = st.number_input("SMTP Port", value=int(email_config.get("port", 587)), key="smtp_port")
            gonderen = st.text_input("Gönderen Email", value=email_config.get("gonderen", ""), placeholder="ornek@gmail.com", key="gonderen_email")
            sifre = st.text_input("Uygulama Şifresi", value=email_config.get("sifre", ""), type="password", key="sifre_email",
                                  help="Gmail için: google.com/account > Güvenlik > Uygulama şifreleri")
            alici = st.text_input("Alıcı Email (opsiyonel)", value=email_config.get("alici", ""), placeholder="Gönderen ile aynı ise boş bırakın", key="alici_email")

            if st.form_submit_button("💾 Email Ayarlarını Kaydet", type="primary", use_container_width=True):
                yeni_config = {
                    "smtp_server": smtp_server,
                    "port": int(smtp_port),
                    "gonderen": gonderen,
                    "sifre": sifre,
                    "alici": alici or gonderen,
                }
                dosya_yaz(EMAIL_FILE, yeni_config)
                st.success("Email ayarları kaydedildi!")
                st.rerun()

        st.divider()
        st.subheader("Manuel Email Gönderimi")

        yaklasan = yaklasan_beyannameler(datetime.now(), 30)
        if yaklasan:
            konu, icerik = email_icerik_olustur(yaklasan)
            with st.expander("📧 Email İçeriği Önizleme", expanded=False):
                st.text_area("Konu", value=konu, disabled=True, key="onizleme_konu")
                st.text_area("İçerik", value=icerik, disabled=True, height=200, key="onizleme_icerik")

            if st.button("📧 Email Gönder", type="primary", use_container_width=True, key="by_email_gonder"):
                if not email_config.get("gonderen") or not email_config.get("sifre"):
                    st.warning("⚠️ Email ayarları yapılandırılmamış. Önce yukarıdaki formu doldurun.")
                else:
                    with st.spinner("Email gönderiliyor..."):
                        from veritabani import email_gonder
                        basarili = email_gonder(konu, icerik)
                    if basarili:
                        st.success("✅ Email gönderildi!")
                    else:
                        st.error("❌ Email gönderilemedi. SMTP ayarlarını kontrol edin.")
        else:
            st.info("Yaklaşan 30 gün içinde beyanname yok, email göndermeye gerek yok.")

        st.divider()
        st.subheader("Otomatik Hatırlatma Kuralları")
        st.caption("Hangi günlerde hatırlatma emaili gönderilsin?")
        kurallar = {
            "T-7": "7 gün kala",
            "T-3": "3 gün kala",
            "T-1": "1 gün kala",
            "T-0": "Bugün (son gün)",
        }
        secili_kurallar = {}
        for k, v in kurallar.items():
            secili_kurallar[k] = st.checkbox(v, value=True, key=f"kur_{k}")

        if st.button("💾 Hatırlatma Kurallarını Kaydet", key="kural_kaydet"):
            kural_config = {"hatirlatma_gunleri": [int(k.replace("T-", "")) if k != "T-0" else 0 for k, v in secili_kurallar.items() if v]}
            dosya_yaz(os.path.join(DATA_DIR, "hatirlatma_kurallari.json"), kural_config)
            st.success("Hatırlatma kuralları kaydedildi!")


def _page_efatura_sorgu():
    """E-fatura mükellef sorgu + Nilvera entegrasyonu."""
    from e_fatura_sorgu import (
        gib_efatura_sorgula, toplu_sorgula, sorgu_ozet,
        vergi_no_dogrula, vkn_algo_dogrula, tckn_algo_dogrula,
        nilvera_config_yukle, nilvera_config_kaydet,
        nilvera_sorgula, nilvera_toplu_sorgula, nilvera_fatura_listesi,
        nilvera_fatura_detay, nilvera_earsiv_indir, nilvera_ozet,
        nilvera_fatura_olustur, nilvera_fatura_gonder, nilvera_fatura_iptal,
    )

    st.header("E-Fatura Mükellef Sorgu")
    st.caption("GİB e-fatura mükellefiyet kontrolü + Nilvera API entegrasyonu")

    nilvera_cfg = nilvera_config_yukle()
    if not nilvera_cfg.get("api_key"):
        st.info("ℹ️ GİB e-fatura public API'si artık doğrudan erişilebilir değil. "
                "Sorgu için bir e-Fatura entegratörü (Nilvera önerilir) kullanın. "
                "Aşağıdaki 'Nilvera Ayarları' sekmesinden API anahtarı girebilirsiniz.")

    tab_gib, tab_nilvera, tab_ayarlar = st.tabs(["🏛️ GİB Sorgu", "🔗 Nilvera API", "⚙️ Nilvera Ayarları"])

    # ── TAB 1: GİB Sorgu ──
    with tab_gib:
        col_i1, col_i2 = st.columns([3, 1])
        with col_i1:
            vkn_input = st.text_input("Vergi/TC Kimlik No", placeholder="1234567890 veya 11111111111", key="efatura_vkn")
        with col_i2:
            sorgula_btn = st.button("🔍 Sorgula", type="primary", use_container_width=True, key="efatura_sorgula_btn")

        if sorgula_btn and vkn_input:
            vkn_temiz = re.sub(r"\D", "", vkn_input)
            if not vergi_no_dogrula(vkn_temiz):
                st.error("Geçersiz format. 10 hane (VKN) veya 11 hane (TCKN) girin.")
            elif len(vkn_temiz) == 10 and not vkn_algo_dogrula(vkn_temiz):
                st.error("VKN algoritma doğrulaması başarısız. Numara yanlış olabilir.")
            elif len(vkn_temiz) == 11 and not tckn_algo_dogrula(vkn_temiz):
                st.error("TCKN algoritma doğrulaması başarısız. Numara yanlış olabilir.")
            else:
                with st.spinner("Sorgulanıyor..."):
                    sonuc = gib_efatura_sorgula(vkn_temiz)

                c1, c2, c3 = st.columns(3)
                with c1:
                    if sonuc.get("efatura"):
                        st.success("✅ E-Fatura")
                    else:
                        st.error("❌ E-Fatura")
                with c2:
                    if sonuc.get("earsiv"):
                        st.success("✅ E-Arşiv")
                    else:
                        st.error("❌ E-Arşiv")
                with c3:
                    st.metric("VKN", vkn_temiz)

                if sonuc.get("unvan"):
                    st.info(f"**Ünvan:** {sonuc['unvan']}")
                if sonuc.get("hata"):
                    st.warning(f"⚠️ {sonuc['hata']}")
                else:
                    st.caption(f"Kaynak: {sonuc.get('kaynak', '?')}")

        st.divider()
        st.subheader("Toplu Sorgu")
        st.caption("Her satıra bir VKN/TCKN yazın, virgül veya yeni satırla ayırın")
        toplu_text = st.text_area("VKN listesi (virgül veya yeni satırla)", height=120,
                                    placeholder="1234567890\n11111111111\n9876543210", key="efatura_toplu")
        if st.button("🔍 Toplu Sorgula", type="primary", key="efatura_toplu_btn") and toplu_text:
            vkn_list = re.split(r"[,\n\s]+", toplu_text)
            vkn_list = [v for v in vkn_list if v.strip()]
            vkn_list = [re.sub(r"\D", "", v) for v in vkn_list]
            vkn_list = [v for v in vkn_list if vergi_no_dogrula(v)]
            if not vkn_list:
                st.error("Geçerli VKN/TCKN bulunamadı.")
            else:
                progress = st.progress(0.0, text="Sorgulanıyor...")
                sonuclar = []
                for i, v in enumerate(vkn_list):
                    s = gib_efatura_sorgula(v)
                    sonuclar.append(s)
                    progress.progress((i + 1) / len(vkn_list), text=f"{i+1}/{len(vkn_list)} tamamlandı")
                import pandas as pd
                df = pd.DataFrame([{
                    "VKN": s["vkn"],
                    "E-Fatura": "✅" if s.get("efatura") else "❌",
                    "E-Arşiv": "✅" if s.get("earsiv") else "❌",
                    "Ünvan": s.get("unvan", "")[:30],
                    "Hata": s.get("hata", "")[:50] or "-",
                } for s in sonuclar])
                st.dataframe(df, width="stretch", hide_index=True)

    # ── TAB 2: Nilvera API ──
    with tab_nilvera:
        config = nilvera_config_yukle()
        if not config.get("api_key"):
            st.warning("⚠️ Nilvera API anahtarı tanımlı değil. 'Nilvera Ayarları' sekmesinden girin.")
        else:
            st.success("🟢 Nilvera API bağlı")

            col_n1, col_n2 = st.columns([3, 1])
            with col_n1:
                nilvera_vkn = st.text_input("VKN/TCKN Sorgula", placeholder="1234567890", key="nilvera_vkn")
            with col_n2:
                nilvera_btn = st.button("🔍 Nilvera Sorgula", type="primary", use_container_width=True, key="nilvera_sorgula_btn")

            if nilvera_btn and nilvera_vkn:
                vkn_temiz = re.sub(r"\D", "", nilvera_vkn)
                if not vergi_no_dogrula(vkn_temiz):
                    st.error("Geçersiz VKN/TCKN formatı.")
                else:
                    with st.spinner("Nilvera API sorgulanıyor..."):
                        sonuc = nilvera_sorgula(vkn_temiz)

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if sonuc.get("efatura"):
                            st.success("✅ E-Fatura")
                        else:
                            st.error("❌ E-Fatura")
                    with c2:
                        if sonuc.get("earsiv"):
                            st.success("✅ E-Arşiv")
                        else:
                            st.error("❌ E-Arşiv")
                    with c3:
                        st.metric("VKN", vkn_temiz)

                    if sonuc.get("unvan"):
                        st.info(f"**Ünvan:** {sonuc['unvan']}")
                    if sonuc.get("adi_soyadi"):
                        st.info(f"**Adı Soyadı:** {sonuc['adi_soyadi']}")
                    if sonuc.get("vergi_dairesi"):
                        st.info(f"**Vergi Dairesi:** {sonuc['vergi_dairesi']}")
                    if sonuc.get("hata"):
                        st.warning(f"⚠️ {sonuc['hata']}")
                    else:
                        st.caption(f"Kaynak: {sonuc.get('kaynak', '?')}")

            st.divider()
            st.subheader("Fatura İşlemleri")

            tab_liste, tab_olustur = st.tabs(["📋 Fatura Listesi", "➕ Yeni Fatura Oluştur"])

            with tab_liste:
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    fatura_vkn = st.text_input("VKN (boş = tümü)", key="nilvera_fatura_vkn")
                with col_f2:
                    fatura_bas = st.date_input("Başlangıç", key="nilvera_fatura_bas")
                with col_f3:
                    fatura_bit = st.date_input("Bitiş", key="nilvera_fatura_bit")

                if st.button("📋 Fatura Listesi Getir", key="nilvera_fatura_listesi_btn"):
                    bas_str = fatura_bas.strftime("%Y-%m-%d") if fatura_bas else None
                    bit_str = fatura_bit.strftime("%Y-%m-%d") if fatura_bit else None
                    with st.spinner("Faturalar çekiliyor..."):
                        sonuc = nilvera_fatura_listesi(
                            vkn=fatura_vkn if fatura_vkn else None,
                            baslangic=bas_str, bitis=bit_str,
                        )
                    if sonuc.get("hata"):
                        st.error(f"❌ {sonuc['hata']}")
                    elif sonuc.get("faturalar"):
                        st.success(f"✅ {sonuc['toplam']} fatura bulundu")
                        import pandas as pd
                        df = pd.DataFrame(sonuc["faturalar"])
                        st.dataframe(df, width="stretch", hide_index=True)

                        fatura_id_secim = st.text_input("Fatura ID (işlem için)", key="fatura_id_secim")
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            if st.button("📥 PDF İndir", key="fatura_pdf_indir") and fatura_id_secim:
                                with st.spinner("İndiriliyor..."):
                                    indir = nilvera_earsiv_indir(fatura_id_secim)
                                if indir.get("dosya_yolu"):
                                    st.success(f"İndirildi: {indir['dosya_yolu']}")
                                else:
                                    st.error(f"❌ {indir.get('hata', 'İndirme başarısız')}")
                        with col_b:
                            if st.button("📤 Gönder", key="fatura_gonder") and fatura_id_secim:
                                with st.spinner("Gönderiliyor..."):
                                    gonder = nilvera_fatura_gonder(fatura_id_secim)
                                if gonder.get("basarili"):
                                    st.success(f"Gönderildi! Durum: {gonder.get('durum')}")
                                else:
                                    st.error(f"❌ {gonder.get('hata', 'Gönderme başarısız')}")
                        with col_c:
                            if st.button("❌ İptal Et", key="fatura_iptal") and fatura_id_secim:
                                with st.spinner("İptal ediliyor..."):
                                    iptal = nilvera_fatura_iptal(fatura_id_secim)
                                if iptal.get("basarili"):
                                    st.success("Fatura iptal edildi!")
                                else:
                                    st.error(f"❌ {iptal.get('hata', 'İptal başarısız')}")
                    else:
                        st.info("Sonuç bulunamadı.")

            with tab_olustur:
                st.caption("Yeni e-arşiv veya e-fatura oluşturun")
                with st.form("yeni_fatura_form", clear_on_submit=False):
                    fatura_tipi = st.selectbox("Fatura Tipi", ["Earsiv", "Efatura"], key="fatura_tipi")
                    gonderen_vkn = st.text_input("Sizin VKN'niz", key="gonderen_vkn")
                    alici_vkn = st.text_input("Alıcı VKN", key="alici_vkn")
                    alici_unvan = st.text_input("Alıcı Ünvanı", key="alici_unvan")
                    fatura_tarih = st.date_input("Fatura Tarihi", key="fatura_tarih")
                    para_birimi = st.selectbox("Para Birimi", ["TRY", "USD", "EUR"], key="para_birimi")

                    st.markdown("**Fatura Kalemleri**")
                    kalem_aciklama = st.text_input("Açıklama", placeholder="Mal/Hizmet açıklaması", key="kalem_aciklama")
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        kalem_miktar = st.number_input("Miktar", min_value=0.01, value=1.0, key="kalem_miktar")
                    with col_m2:
                        kalem_fiyat = st.number_input("Birim Fiyat", min_value=0.01, value=100.0, key="kalem_fiyat")
                    with col_m3:
                        kalem_kdv = st.selectbox("KDV %", [0, 1, 10, 20], index=3, key="kalem_kdv")

                    kalem_tutar = kalem_miktar * kalem_fiyat
                    kdv_tutari = round(kalem_tutar * kalem_kdv / 100, 2)
                    genel_toplam = kalem_tutar + kdv_tutari

                    col_t1, col_t2, col_t3 = st.columns(3)
                    with col_t1:
                        st.metric("Matrah", f"{kalem_tutar:,.2f} TL")
                    with col_t2:
                        st.metric("KDV", f"{kdv_tutari:,.2f} TL")
                    with col_t3:
                        st.metric("Genel Toplam", f"{genel_toplam:,.2f} TL")

                    if st.form_submit_button("➕ Fatura Oluştur", type="primary", use_container_width=True):
                        if not gonderen_vkn or not alici_vkn:
                            st.error("VKN'ler zorunludur.")
                        elif not vergi_no_dogrula(gonderen_vkn) or not vergi_no_dogrula(alici_vkn):
                            st.error("Geçersiz VKN formatı.")
                        else:
                            fatura_veri = {
                                "faturaTipi": fatura_tipi,
                                "gonderenVkn": re.sub(r"\D", "", gonderen_vkn),
                                "aliciVkn": re.sub(r"\D", "", alici_vkn),
                                "aliciUnvani": alici_unvan,
                                "tarih": fatura_tarih.strftime("%Y-%m-%d"),
                                "paraBirimi": para_birimi,
                                "kalemler": [{
                                    "aciklama": kalem_aciklama or "Mal/Hizmet",
                                    "miktar": kalem_miktar,
                                    "birimFiyat": kalem_fiyat,
                                    "kdvOrani": kalem_kdv,
                                    "tutar": kalem_tutar,
                                }],
                                "toplamTutar": kalem_tutar,
                                "kdvToplami": kdv_tutari,
                                "genelToplam": genel_toplam,
                            }
                            with st.spinner("Fatura oluşturuluyor..."):
                                sonuc = nilvera_fatura_olustur(fatura_veri)
                            if sonuc.get("fatura_id"):
                                st.success(f"Fatura oluşturuldu! ID: {sonuc['fatura_id']}")
                                if st.button("📤 Hemen Gönder", key="yeni_fatura_gonder"):
                                    with st.spinner("Gönderiliyor..."):
                                        gonder = nilvera_fatura_gonder(sonuc["fatura_id"])
                                    if gonder.get("basarili"):
                                        st.success(f"Gönderildi! Durum: {gonder.get('durum')}")
                                    else:
                                        st.error(f"❌ {gonder.get('hata')}")
                            else:
                                st.error(f"❌ {sonuc.get('hata', 'Oluşturma başarısız')}")

    # ── TAB 3: Nilvera Ayarları ──
    with tab_ayarlar:
        st.subheader("Nilvera API Ayarları")
        st.caption("api.nilvera.com'dan API anahtarı almanız gerekir.")

        config = nilvera_config_yukle()
        with st.form("nilvera_ayarlar_form", clear_on_submit=False):
            api_key = st.text_input("API Anahtarı", value=config.get("api_key", ""),
                                     type="password", key="nilvera_api_key")
            base_url = st.text_input("API Base URL", value=config.get("base_url", "https://api.nilvera.com"),
                                      key="nilvera_base_url")
            aktif = st.checkbox("Nilvera API aktif", value=config.get("aktif", False), key="nilvera_aktif")

            if st.form_submit_button("💾 Kaydet", type="primary", use_container_width=True):
                yeni_config = {"api_key": api_key, "base_url": base_url, "aktif": aktif}
                sonuc = nilvera_config_kaydet(yeni_config)
                if sonuc["basarili"]:
                    st.success(f"✅ {sonuc['mesaj']}")
                else:
                    st.error(f"❌ {sonuc['mesaj']}")

        if config.get("api_key"):
            with st.expander("🧪 API Bağlantı Testi"):
                if st.button("Test Sorgusu Yap", key="nilvera_test_btn"):
                    with st.spinner("Test sorgulanıyor..."):
                        test_sonuc = nilvera_sorgula("1234567890")
                    if test_sonuc.get("hata"):
                        st.warning(f"⚠️ {test_sonuc['hata']}")
                    else:
                        st.success("✅ Nilvera API bağlantısı başarılı!")


def _kullanici_yonetimi_paneli():
    """Admin icin kullanici yonetimi paneli."""
    import pandas as pd
    from user_manager import (
        kullanici_listesi_safe, kullanici_ekle, kullanici_sil,
        kullanici_sifre_degistir, kullanici_admin_mi,
        DEFAULT_ADMIN_USERNAME,
    )

    st.subheader("👥 Kullanıcı Yönetimi")
    st.caption("Yeni kullanıcı ekle, şifre değiştir, rol ayarla")

    kullanicilar = kullanici_listesi_safe()
    df = pd.DataFrame([{
        "Kullanıcı": k.get("username"),
        "Ad Soyad": k.get("full_name", ""),
        "Rol": "👑 Admin" if k.get("role") == "admin" else "👤 User",
        "E-posta": k.get("email", "") or "-",
        "Durum": "✅ Aktif" if k.get("aktif", True) else "❌ Pasif",
        "Şifre": k.get("password_gizli", "••••"),
        "Oluşturma": k.get("olusturma", "?"),
    } for k in kullanicilar])
    st.dataframe(df, width="stretch", hide_index=True)

    col_a, col_b = st.columns(2)

    with col_a:
        with st.expander("➕ Yeni Kullanıcı Ekle", expanded=False):
            with st.form("yeni_kullanici_form", clear_on_submit=True):
                yeni_username = st.text_input("Kullanıcı Adı", placeholder="mehmet")
                yeni_full = st.text_input("Ad Soyad", placeholder="Mehmet Yılmaz")
                yeni_email = st.text_input("E-posta (opsiyonel)", placeholder="mehmet@firma.com")
                yeni_sifre = st.text_input("Şifre (min 4)", type="password")
                yeni_sifre2 = st.text_input("Şifre Tekrar", type="password")
                yeni_role = st.selectbox("Rol", ["user", "admin"])
                ekle_submit = st.form_submit_button("Ekle", type="primary", use_container_width=True)
                if ekle_submit:
                    if yeni_sifre != yeni_sifre2:
                        st.error("Şifreler eşleşmiyor")
                    else:
                        sonuc = kullanici_ekle(yeni_username, yeni_sifre, yeni_role, yeni_full, yeni_email)
                        if sonuc["basarili"]:
                            st.success(sonuc["mesaj"])
                            st.rerun()
                        else:
                            st.error(sonuc["mesaj"])

    with col_b:
        with st.expander("🔑 Şifre Değiştir", expanded=False):
            with st.form("sifre_degistir_form", clear_on_submit=True):
                mevcut_user = st.session_state.get("current_user", {}).get("username", "")
                target_user = st.text_input("Kullanıcı Adı", value=mevcut_user)
                eski_sifre = st.text_input("Mevcut Şifre", type="password")
                yeni_sifre1 = st.text_input("Yeni Şifre", type="password")
                yeni_sifre2 = st.text_input("Yeni Şifre Tekrar", type="password")
                sifre_submit = st.form_submit_button("Şifre Değiştir", type="primary", use_container_width=True)
                if sifre_submit:
                    if yeni_sifre1 != yeni_sifre2:
                        st.error("Yeni şifreler eşleşmiyor")
                    else:
                        sonuc = kullanici_sifre_degistir(target_user, eski_sifre, yeni_sifre1)
                        if sonuc["basarili"]:
                            st.success(sonuc["mesaj"])
                        else:
                            st.error(sonuc["mesaj"])

    with st.expander("🗑️ Kullanıcı Sil", expanded=False):
        st.warning("⚠️ Bu işlem geri alınamaz!")
        col_x, col_y = st.columns([3, 1])
        with col_x:
            sil_username = st.text_input("Silinecek Kullanıcı Adı", key="sil_input")
        with col_y:
            st.write("")
            st.write("")
            if st.button("🗑️ Sil", type="primary", key="sil_btn"):
                sonuc = kullanici_sil(sil_username)
                if sonuc["basarili"]:
                    st.success(sonuc["mesaj"])
                    st.rerun()
                else:
                    st.error(sonuc["mesaj"])

    st.caption(f"💡 İlk kurulum: **{DEFAULT_ADMIN_USERNAME}** / **admin123** (ilk girişte değiştirin!)")
