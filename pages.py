import os
import io
import re
import glob
import shutil
from datetime import datetime, timedelta
from PIL import Image
import pandas as pd
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


def _page_z_raporu_yukle(hesap_kodlari):
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
        progress = st.progress(0, text="OCR yapılıyor...")
        baslama = _time.time()
        tamamlanan = [0]
        all_results = [None] * toplam

        def _tek_ocr(idx, fname, data):
            try:
                if fname.lower().endswith(".pdf"):
                    if not PDF2IMAGE_MEVCUT:
                        return idx, {"filename": fname, "error": "pdf2image yok", "ocr_text": ""}
                    pages = convert_from_bytes(data, dpi=300)
                    sonuclar = []
                    for pi, page in enumerate(pages):
                        ocr_text = ocr_gorsel_isle_cached(page.convert("RGB"))
                        parsed = parse_z_raporu(ocr_text)
                        ogr_alanlari_uygula(parsed)
                        parsed["filename"] = f"{fname} - Syf {pi+1}"
                        parsed["ocr_text"] = ocr_text
                        parsed["mukellef_adi"] = ""
                        sonuclar.append(parsed)
                    return idx, sonuclar
                else:
                    img = Image.open(io.BytesIO(data))
                    ocr_text = ocr_gorsel_isle_cached(img)
                    parsed = parse_z_raporu(ocr_text)
                    ogr_alanlari_uygula(parsed)
                    parsed["filename"] = fname
                    parsed["ocr_text"] = ocr_text
                    parsed["mukellef_adi"] = ""
                    return idx, parsed
            except Exception as e:
                log.error(f"OCR hatasi {fname}: {e}")
                return idx, {"filename": fname, "error": str(e), "ocr_text": ""}

        max_workers = min(4, toplam)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_tek_ocr, i, fname, data): i
                for i, (fname, data) in enumerate(dosya_verileri)
            }
            for future in as_completed(futures):
                idx, result = future.result()
                tamamlanan[0] += 1
                if isinstance(result, list):
                    all_results[idx] = result
                else:
                    all_results[idx] = result
                gecen = _time.time() - baslama
                ort = gecen / max(tamamlanan[0], 1)
                kal = max(toplam - tamamlanan[0], 0) * ort
                kstr = f"{int(kal//60)}dk {int(kal%60)}sn" if kal >= 60 else f"{int(kal)}sn"
                gstr = f"{int(gecen//60)}dk {int(gecen%60)}sn" if gecen >= 60 else f"{gecen:.1f}sn"
                progress.progress(tamamlanan[0] / max(toplam, 1), text=f"{tamamlanan[0]}/{toplam} | {gstr} gecti | ~{kstr} kaldi")

        flat_results = []
        for r in all_results:
            if isinstance(r, list):
                flat_results.extend(r)
            else:
                flat_results.append(r)
        all_results = flat_results

        toplam_sure = _time.time() - baslama
        sure_metni = f"{int(toplam_sure//60)}dk {int(toplam_sure%60)}sn" if toplam_sure >= 60 else f"{toplam_sure:.1f}sn"
        progress.progress(1.0, text=f"OCR tamamlandi! Toplam: {sure_metni} ({toplam} dosya, {max_workers} paralel)")

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

        if len(results) > 1:
            tab_labels = [f"📄 {r.get('filename','?')[:18]}" for r in results]
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
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.text_input("Tarih", value=r.get("tarih") or "", key=f"ed_tarih_{tab_idx}")
                    st.text_input("Firma", value=r.get("firma_adi") or "", key=f"ed_firma_{tab_idx}")
                    st.text_input("Banka", value=r.get("banka_adi") or "", key=f"ed_banka_{tab_idx}")
                    st.text_input("Z No", value=r.get("z_no") or "", key=f"ed_zno_{tab_idx}")
                with c2:
                    st.number_input("Brüt (TL)", min_value=0.0, value=float(r.get("brut", 0)), step=100.0, key=f"ed_brut_{tab_idx}")
                    st.number_input("Net (TL)", min_value=0.0, value=float(r.get("net_toplam", 0)), step=100.0, key=f"ed_net_{tab_idx}")
                    st.number_input("Nakit (TL)", min_value=0.0, value=float(r.get("nakit", 0)), step=100.0, key=f"ed_nakit_{tab_idx}")
                with c3:
                    st.number_input("K.Kartı (TL)", min_value=0.0, value=float(r.get("kredi_karti", 0)), step=100.0, key=f"ed_kk_{tab_idx}")
                    st.number_input("Yemek Çeki (TL)", min_value=0.0, value=float(r.get("yemek_ceki", 0)), step=100.0, key=f"ed_yemek_{tab_idx}")
                    st.number_input("İade (TL)", min_value=0.0, value=float(r.get("iadeler", 0)), step=100.0, key=f"ed_iade_{tab_idx}")

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
                    # session_state'i guncelle (referans ayni, degisiklikler zaten kaydedildi)
                    st.session_state.results = results
                    if ogr_sayisi > 0:
                        st.toast(f"✅ {ogr_sayisi} alan öğrenildi! Sonraki OCR'da otomatik uygulanacak.", icon="✅")
                    else:
                        st.toast(f"✅ {len(degisiklik)} tutar güncellendi.", icon="✅")
                    if degisiklik:
                        with st.expander("📋 Yapılan değişiklikler", expanded=True):
                            for d in degisiklik:
                                st.write(f"- {d}")
                    if eslesme_ekisik:
                        with st.expander("⚠️ Öğrenilemeyen detay düzeltmeler (ham OCR'da eşleşme bulunamadı, ama alan varsayılanı kaydedildi)", expanded=False):
                            for alan, dogru, yanlis in eslesme_ekisik:
                                st.write(f"- **{alan}**: '{dogru}' için ham OCR'da benzer satır bulunamadı")
                            st.info("Yine de alan varsayılanı kaydedildi — sonraki OCR'da otomatik uygulanacak.")
                    st.rerun()

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
            try:
                gecmis_kaydet(results, hesap_kodlari, st.session_state.get("secili_mukellef", ""))
            except Exception as e:
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
            st.session_state.pop("results", None)
            st.session_state.pop("processed", None)
            st.success("Düzenlenen veriler geçmişe kaydedildi!")
            st.rerun()

        with st.expander("OCR Ham Metinler"):
            for i, r in enumerate(results):
                if "error" not in r:
                    st.markdown(f"**{i+1}. {r.get('filename','')} — Z No: {r.get('z_no','?')}**")
                    st.text(r.get("ocr_text", ""))
                    st.divider()


def _page_dashboard():
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

        st.divider()
        st.subheader("Karşılaştırma")
        now = datetime.now()
        bu_ay = now.month
        bu_yil = now.year
        gecen_ay = bu_ay - 1 if bu_ay > 1 else 12
        gecen_ay_yil = bu_yil if bu_ay > 1 else bu_yil - 1
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
                if d.year == bu_yil and d.month == bu_ay:
                    bu_ay_ciro += net
                if d.year == gecen_ay_yil and d.month == gecen_ay:
                    gecen_ay_ciro += net
            except (ValueError, TypeError):
                continue
        ay_fark = bu_ay_ciro - gecen_ay_ciro
        yil_fark = bu_yil_ciro - gecen_yil_ciro
        ay_yuzde = (ay_fark / gecen_ay_ciro * 100) if gecen_ay_ciro > 0 else 0
        yil_yuzde = (yil_fark / gecen_yil_ciro * 100) if gecen_yil_ciro > 0 else 0
        comp1, comp2, comp3, comp4 = st.columns(4)
        comp1.metric(f"Bu Ay ({bu_ay})", f"{bu_ay_ciro:,.0f} TL", f"{ay_fark:+,.0f} TL ({ay_yuzde:+.1f}%)")
        comp2.metric(f"Geçen Ay ({gecen_ay})", f"{gecen_ay_ciro:,.0f} TL")
        comp3.metric(f"Bu Yıl ({bu_yil})", f"{bu_yil_ciro:,.0f} TL", f"{yil_fark:+,.0f} TL ({yil_yuzde:+.1f}%)")
        comp4.metric(f"Geçen Yıl ({bu_yil-1})", f"{gecen_yil_ciro:,.0f} TL")

        st.divider()
        st.subheader("Aylık Ciro Trendi")
        aylik_ciro = {}
        for f in tum_fisler:
            t = f.get("tarih", "")
            try:
                d = datetime.strptime(t, "%d.%m.%Y")
                ay_anahtar = d.strftime("%Y-%m")
                aylik_ciro[ay_anahtar] = aylik_ciro.get(ay_anahtar, 0) + (f.get("net_toplam", 0) or 0)
            except (ValueError, TypeError):
                continue
        if aylik_ciro:
            sirali = sorted(aylik_ciro.items())
            trend_df = pd.DataFrame(sirali, columns=["Ay", "Ciro"])
            trend_df = trend_df.set_index("Ay")
            st.line_chart(trend_df, height=300)


def _page_fis_gecmisi(hesap_kodlari):
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
                            st.success("Fiş güncellendi!")
                            st.rerun()
                        else:
                            st.error("Güncelleme başarısız oldu.")

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


def _page_ayarlar():
    st.header("Ayarlar")

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
