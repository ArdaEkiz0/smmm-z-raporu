import io
import html as html_mod
from datetime import datetime

from config import BASIT_USUL_KOLONLAR, SABLON_FILE, URUN_KODLARI_FILE
from utils import dosya_oku, log, parse_tutar


def varsayilan_kodlar():
    return {
        "kredi_karti": "108.01", "nakit": "100.01", "yemek_ceki": "108.03",
        "satis_1": "600.01", "satis_10": "600.05",
        "satis_20": "600.04",
        "kdv_1": "391.01", "kdv_10": "391.05",
        "kdv_20": "391.04", "iadeler": "610.01",
    }


HESAP_PLANLARI = {
    "LUCA": varsayilan_kodlar(),
    "Logo": {
        "kredi_karti": "100.02", "nakit": "100.01", "yemek_ceki": "100.03",
        "satis_1": "601.01", "satis_10": "601.02",
        "satis_20": "601.03",
        "kdv_1": "391.01", "kdv_10": "391.02",
        "kdv_20": "391.03", "iadeler": "602.01",
    },
    "Netsis": {
        "kredi_karti": "120.01", "nakit": "100.01", "yemek_ceki": "120.02",
        "satis_1": "600.01", "satis_10": "600.02",
        "satis_20": "600.03",
        "kdv_1": "391.01", "kdv_10": "391.02",
        "kdv_20": "391.03", "iadeler": "610.01",
    },
}


def urun_kodlari_varsayilan():
    return [
        {"pattern": "EKMEK", "hesap_kodu": "600.06", "aciklama": "Ekmek Satışı", "kdv_orani": 1},
        {"pattern": "SİGARA", "hesap_kodu": "600.07", "aciklama": "Sigara Satışı", "kdv_orani": 0},
        {"pattern": "SIGARA", "hesap_kodu": "600.07", "aciklama": "Sigara Satışı", "kdv_orani": 0},
        {"pattern": "SÜT", "hesap_kodu": "600.08", "aciklama": "Süt ve Süt Ürünleri", "kdv_orani": 10},
    ]


def urun_kodlari_yukle():
    return dosya_oku(URUN_KODLARI_FILE, urun_kodlari_varsayilan())


def urun_kodlari_kaydet(kodlar):
    dosya_yaz(URUN_KODLARI_FILE, kodlar)


def urun_kodu_bul(urun_kodlari, urun_adi):
    if not urun_adi or not urun_kodlari:
        return None
    ua = urun_adi.upper().strip()
    import re
    for uk in urun_kodlari:
        pat = uk.get("pattern", "")
        if pat and re.search(re.escape(pat), ua, re.IGNORECASE):
            return uk
    return None


def _iade_dagit(iade, nakit, kk, yemek):
    """İade tutarını kaynaklara (nakit, KK, yemek) sırayla dağıt.
    Döndürür: (iade_nkt_k, iade_kk_k, iade_yem_k, yeni_nakit, yeni_kk, yeni_yemek)."""
    if iade <= 0:
        return 0, 0, 0, nakit, kk, yemek
    iade_kk_k = round(min(kk, iade), 2) if kk > 0 else 0
    iade_nkt_k = round(min(nakit, iade - iade_kk_k), 2) if nakit > 0 and iade > iade_kk_k else 0
    iade_yem_k = round(iade - iade_kk_k - iade_nkt_k, 2)
    yeni_nakit = round(nakit - iade_nkt_k, 2) if iade_nkt_k > 0 else nakit
    yeni_kk = round(kk - iade_kk_k, 2) if iade_kk_k > 0 else kk
    yeni_yemek = round(yemek - iade_yem_k, 2) if iade_yem_k > 0 else yemek
    return iade_nkt_k, iade_kk_k, iade_yem_k, yeni_nakit, yeni_kk, yeni_yemek


def data_to_luca_rows(data, hesap_kodlari, fis_no=1, urun_kodlari=None):
    rows = []

    def satir(hesap_kodu, aciklama, borc, alacak):
        return {
            "İŞLEM": "1", "KATEGORİ": "Defter Fişleri", "BELGE TÜRÜ": "Z Raporu",
            "BELGE TARİHİ": data.get("tarih", ""), "FİŞ TARİHİ": data.get("tarih", ""),
            "FİŞ NO": str(fis_no), "BELGE NO": data.get("z_no", ""),
            "MÜKELLEF/ALICI TC KİMLİK NO": "", "BAĞLI OLDUĞU VERGİ DAİRESİ": "",
            "MÜKELLEF/ALICI ÜNVAN": data.get("firma_adi", "") or data.get("mukellef_adi", ""),
            "MÜKELLEF/ALICI SOYADI": "", "ADRES": "", "PLAKA NO": "", "KİLOMETRE": "",
            "CİNSİ": "", "GİDER TÜRÜ": "", "KDV Oranları GİRİŞ": "", "KDV Oranları ÇIKIŞ": "",
            "STOK KODU": "", "MALZEME/HİZMET ADI": aciklama,
            "MİKTAR": "", "BİRİM FİYAT": "", "TUTAR": "", "TUTAR (TL)": "",
            "KDV ORANI (%)": "", "İSKONTO ORANI (%)": "", "İSKONTO TUTARI (TL)": "",
            "VERGİLER DAHİL TOPLAM": "", "KDV TUTARI": "", "GENEL TOPLAM": "",
            "KREDİ KARTI İLE TAHSİLAT": "", "TAHSİL EDİLEN": "",
            "KALEM SAYISI": "", "SIRA NO": "", "ÖZEL KOD": "",
            "AÇIKLAMA": aciklama,
            "Hesap Kodu": hesap_kodu, "Borç": borc, "Alacak": alacak,
        }

    net_toplam = data.get("net_toplam", 0) or 0
    nakit = data.get("nakit", 0) or 0
    kk = data.get("kredi_karti", 0) or 0
    yemek = data.get("yemek_ceki", 0) or 0
    iade = data.get("iadeler", 0) or 0
    musteri = data.get("firma_adi", "") or data.get("mukellef_adi", "") or "Müşteri"
    brut = data.get("brut", 0) or 0

    # Z raporundan KDV hesapla: Brüt (KDV dahil) - Net (KDV hariç) = KDV
    z_toplam_kdv = round(brut - net_toplam, 2) if brut > 0 and net_toplam > 0 else 0

    # Ürün bazlı satışlar - Z raporu degerlerine gore orantili dagilim
    urunler = data.get("urunler", [])
    if urunler:
        toplam_urun_tutari = sum(u.get("tutar", 0) or 0 for u in urunler)

        # Urunlerin toplam tutarini net_toplam'a esle (orantili dagilim)
        if toplam_urun_tutari > 0 and net_toplam > 0:
            oran = net_toplam / toplam_urun_tutari
        else:
            oran = 1.0

        for u in urunler:
            urun_adi = u.get("urun", "Ürün")
            tutar = u.get("tutar", 0) or 0
            kdv_orani = u.get("oran", 0) or 0
            # Orantili matrah: urun tutari * oran_katsayisi
            matrah = round(tutar * oran, 2)
            if kdv_orani > 0:
                kdv = round(matrah * kdv_orani / 100, 2)
            else:
                kdv = 0
            satis_kod = "satis_" + str(kdv_orani)
            hesap_kodu = hesap_kodlari.get(satis_kod, hesap_kodlari.get("satis_20", "600.04"))
            satis_idx = len(rows)
            rows.append(satir(hesap_kodu, f"{urun_adi} - {musteri}", 0, matrah))
            if kdv > 0:
                kdv_kod = "kdv_" + str(kdv_orani)
                kdv_hk = hesap_kodlari.get(kdv_kod, hesap_kodlari.get("kdv_20", "391.04"))
                rows.append(satir(kdv_hk, f"KDV %{kdv_orani} - {urun_adi} - {musteri}", 0, kdv))

            if urun_kodlari:
                eslesme = urun_kodu_bul(urun_kodlari, urun_adi)
                if eslesme:
                    urun_kodu = eslesme.get("hesap_kodu", "")
                    rows[satis_idx]["Hesap Kodu"] = urun_kodu

        # Urunlerden hesaplanan toplam KDV ile Z raporu KDV'sini karsilastir
        urun_toplam_kdv = sum((r.get("Alacak", 0) or 0) for r in rows if "KDV" in r.get("AÇIKLAMA", ""))
        urun_toplam_matrah = sum((r.get("Alacak", 0) or 0) for r in rows if "KDV" not in r.get("AÇIKLAMA", ""))

        # KDV farki varsa duzelt (son KDV satirini ayarla)
        kdv_farki = round(z_toplam_kdv - urun_toplam_kdv, 2)
        if abs(kdv_farki) > 0.01 and rows:
            for r in reversed(rows):
                if "KDV" in r.get("AÇIKLAMA", ""):
                    eski_kdv = r.get("Alacak", 0) or 0
                    r["Alacak"] = round(eski_kdv + kdv_farki, 2)
                    break

        if iade > 0:
            _, _, _, nakit, kk, yemek = _iade_dagit(iade, nakit, kk, yemek)
            rows.append(satir(hesap_kodlari.get("iadeler", "610.01"), f"İade - {musteri}", iade, 0))
        if nakit > 0:
            rows.append(satir(hesap_kodlari.get("nakit", "100.01"), f"Nakit Tahsilat - {musteri}", nakit, 0))
        if kk > 0:
            rows.append(satir(hesap_kodlari.get("kredi_karti", "108.01"), f"KK Tahsilat - {musteri}", kk, 0))
        if yemek > 0:
            rows.append(satir(hesap_kodlari.get("yemek_ceki", "108.03"), f"Yemek Çeki - {musteri}", yemek, 0))
        return rows

    # Ürün yok - klasik toplu muhasebe
    kdv_kalemleri = data.get("kdv_kalemleri", [])
    if kdv_kalemleri:
        toplam_kalemden_kdv = sum(kv.get("kdv_tutari", 0) or 0 for kv in kdv_kalemleri)
        for kv in kdv_kalemleri:
            oran = kv.get("oran", 0)
            matrah = kv.get("matrah", 0) or 0
            kdv_t = kv.get("kdv_tutari", 0) or 0
            satis_key = "satis_" + str(oran)
            if matrah > 0:
                rows.append(satir(hesap_kodlari.get(satis_key, "600.04"), f"Satış %{oran} - {musteri}", 0, matrah))
                kdv_key = "kdv_" + str(oran)
                rows.append(satir(hesap_kodlari.get(kdv_key, "391.04"), f"KDV %{oran} - {musteri}", 0, kdv_t))
        if iade > 0:
            _, _, _, nakit, kk, yemek = _iade_dagit(iade, nakit, kk, yemek)
            rows.append(satir(hesap_kodlari.get("iadeler", "610.01"), f"İade - {musteri}", iade, 0))
        if nakit > 0:
            rows.append(satir(hesap_kodlari.get("nakit", "100.01"), f"Nakit Tahsilat - {musteri}", nakit, 0))
        if kk > 0:
            rows.append(satir(hesap_kodlari.get("kredi_karti", "108.01"), f"KK Tahsilat - {musteri}", kk, 0))
        if yemek > 0:
            rows.append(satir(hesap_kodlari.get("yemek_ceki", "108.03"), f"Yemek Çeki - {musteri}", yemek, 0))
        return rows

    # En basit: tek satır satış - Z raporu değerlerini doğrudan kullan
    if net_toplam <= 0 and nakit <= 0 and kk <= 0 and yemek <= 0:
        return rows

    rows.append(satir("600.04", f"Z Raporu Satış - {musteri}", 0, net_toplam))
    if z_toplam_kdv > 0:
        rows.append(satir("391.04", f"KDV - {musteri}", 0, z_toplam_kdv))
    _, _, _, nakit, kk, yemek = _iade_dagit(iade, nakit, kk, yemek)
    if nakit > 0:
        rows.append(satir(hesap_kodlari.get("nakit", "100.01"), f"Nakit Tahsilat - {musteri}", nakit, 0))
    if kk > 0:
        rows.append(satir(hesap_kodlari.get("kredi_karti", "108.01"), f"KK Tahsilat - {musteri}", kk, 0))
    if yemek > 0:
        rows.append(satir(hesap_kodlari.get("yemek_ceki", "108.03"), f"Yemek Çeki - {musteri}", yemek, 0))
    if iade > 0:
        rows.append(satir(hesap_kodlari.get("iadeler", "610.01"), f"İade - {musteri}", iade, 0))
    return rows


def hesapla_luca_rows(results, hesap_kodlari, urun_kodlari):
    all_luca_rows = []
    fc = 1
    for r in results:
        if "error" not in r:
            rows = data_to_luca_rows(r, hesap_kodlari, fc, urun_kodlari)
            all_luca_rows.extend(rows)
            fc += 1
    return all_luca_rows


def generate_mukellef_rapor(fisler, mukellef_adi):
    nakit_toplam = sum(f.get("nakit", 0) or 0 for f in fisler)
    kk_toplam = sum(f.get("kredi_karti", 0) or 0 for f in fisler)
    iade_toplam = sum(f.get("iadeler", 0) or 0 for f in fisler)
    net_toplam = sum(f.get("net_toplam", 0) or 0 for f in fisler)
    brüt_toplam = sum(f.get("brut", 0) or 0 for f in fisler)

    satirlar = ""
    for f in fisler:
        satirlar += f"""<tr>
<td>{html_mod.escape(str(f.get('tarih','?')))}</td>
<td>{html_mod.escape(str(f.get('z_no','?')))}</td>
<td>{html_mod.escape(str(f.get('banka_adi','-')))}</td>
<td style='text-align:right'>{f.get('brut',0):,.2f}</td>
<td style='text-align:right'>{f.get('net_toplam',0):,.2f}</td>
<td style='text-align:right'>{f.get('nakit',0):,.2f}</td>
<td style='text-align:right'>{f.get('kredi_karti',0):,.2f}</td>
<td style='text-align:right'>{f.get('iadeler',0):,.2f}</td>
</tr>"""

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    guvenli_adi = html_mod.escape(str(mukellef_adi))
    html_icerik = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Mükellef Raporu - {guvenli_adi}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; }}
h1 {{ text-align: center; color: #1a5276; }}
.meta {{ text-align: center; color: #666; }}
.ozet {{ display: flex; justify-content: space-around; margin: 20px 0; }}
.ozet > div {{ text-align: center; padding: 10px; background: #e8f6f3; border-radius: 8px; min-width: 120px; }}
.deger {{ font-size: 24px; font-weight: bold; color: #1a5276; }}
.etiket {{ font-size: 12px; color: #666; }}
table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
th, td {{ border: 1px solid #ddd; padding: 6px; }}
th {{ background: #1a5276; color: white; }}
</style></head><body>
<h1>{guvenli_adi}</h1>
<p class="meta">{now} | {len(fisler)} Fiş</p>
<div class="ozet">
<div><div class="deger">{net_toplam:,.2f} ₺</div><div class="etiket">Net Toplam</div></div>
<div><div class="deger">{brüt_toplam:,.2f} ₺</div><div class="etiket">Brüt Toplam</div></div>
<div><div class="deger">{nakit_toplam:,.2f} ₺</div><div class="etiket">Nakit</div></div>
<div><div class="deger">{kk_toplam:,.2f} ₺</div><div class="etiket">Kredi Kartı</div></div>
<div><div class="deger">{iade_toplam:,.2f} ₺</div><div class="etiket">İade</div></div>
</div>
<table>
<tr><th>Tarih</th><th>Z No</th><th>Banka</th><th>Brüt</th><th>Net</th><th>Nakit</th><th>KK</th><th>İade</th></tr>
{satirlar}
<tr style="font-weight:bold;background:#e8f6f3">
<td colspan="3">TOPLAM</td>
<td style='text-align:right'>{brüt_toplam:,.2f}</td>
<td style='text-align:right'>{net_toplam:,.2f}</td>
<td style='text-align:right'>{nakit_toplam:,.2f}</td>
<td style='text-align:right'>{kk_toplam:,.2f}</td>
<td style='text-align:right'>{iade_toplam:,.2f}</td>
</tr>
</table>
<p style="text-align:center;color:#999;margin-top:30px">SMMM Z Raporu ve Fiş Yönetim Sistemi</p>
</body></html>"""
    return html_icerik


def generate_excel(data_rows):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Z Raporlari"

    if not data_rows:
        ws.cell(row=1, column=1, value="Veri Yok")
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.getvalue()

    kolonlar = list(data_rows[0].keys())
    # Remove extra columns
    for ek in ["Hesap Kodu", "Borç", "Alacak"]:
        if ek in kolonlar:
            kolonlar.remove(ek)

    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="1A5276", end_color="1A5276", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    for ci, kolon_adi in enumerate(kolonlar, 1):
        cell = ws.cell(row=1, column=ci, value=kolon_adi)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    for ri, row in enumerate(data_rows, 2):
        for ci, kolon_adi in enumerate(kolonlar, 1):
            cell = ws.cell(row=ri, column=ci, value=row.get(kolon_adi, ""))
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    for col_idx in range(1, len(kolonlar) + 1):
        max_len = 0
        for row_idx in range(1, min(len(data_rows) + 2, 50)):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 3, 45)

    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def generate_excel_cached(data_rows_tuple):
    return generate_excel(list(data_rows_tuple))


def generate_basit_usul_excel(results, muk_bilgi, sablon_data=None):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Serbest Meslek"

    if not results:
        ws.cell(row=1, column=1, value="Veri Yok")
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.getvalue()

    if sablon_data:
        try:
            from openpyxl import load_workbook
            sablon_io = io.BytesIO(sablon_data)
            wb2 = load_workbook(sablon_io)
            ws2 = wb2.active
            basliklar = []
            for col in ws2.iter_cols(1, ws2.max_column, max_row=1):
                basliklar.append(col[0].value or "")
            if basliklar:
                return sablon_data
        except Exception:
            log.warning("Şablon dosyası okunamadı", exc_info=True)

    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="1A5276", end_color="1A5276", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    for ci, kolon_adi in enumerate(BASIT_USUL_KOLONLAR, 1):
        cell = ws.cell(row=1, column=ci, value=kolon_adi)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    tckn = (muk_bilgi or {}).get("vergi_no", "")
    vd = (muk_bilgi or {}).get("vd", "")
    unvan = (muk_bilgi or {}).get("adi", "")
    adres = (muk_bilgi or {}).get("notlar", "")

    def base_row():
        return [""] * len(BASIT_USUL_KOLONLAR)

    def yaz_satir(row, evrak_tarihi, evrak_no, ua, miktar, brut_tutar, oran, kk_ksm):
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
        row[19] = ua
        row[20] = miktar
        birim_f = round(brut_tutar / miktar, 2) if (isinstance(miktar, (int, float)) and miktar > 0) else ""
        row[21] = birim_f
        matrah = round(brut_tutar / (1 + oran / 100), 2) if oran > 0 else brut_tutar
        row[22] = matrah
        row[24] = oran if oran > 0 else ""
        kdv = round(brut_tutar - matrah, 2) if oran > 0 else 0
        row[28] = kdv
        row[29] = brut_tutar
        row[30] = kk_ksm

    ri = 2
    for r in results:
        if "error" in r:
            continue
        evrak_tarihi = r.get("tarih", "")
        evrak_no = r.get("z_no", "") or r.get("belge_no", "")
        kk_tutar = r.get("kredi_karti", 0) or 0
        toplam_tahsilat = r.get("toplam_tahsilat", 0) or r.get("brut", 0) or 1
        kk_orani = kk_tutar / max(toplam_tahsilat, 1)
        urunler = r.get("urunler", [])
        if not urunler:
            row = base_row()
            brut = r.get("brut", 0) or toplam_tahsilat or 0
            kk_ksm = round(brut * kk_orani, 2)
            yaz_satir(row, evrak_tarihi, evrak_no, "", "", brut, 0, kk_ksm)
            for ci, val in enumerate(row):
                ws.cell(row=ri, column=ci + 1, value=val).border = thin_border
            ri += 1
            continue
        for urun in urunler:
            row = base_row()
            ua = urun.get("urun", "")
            miktar = urun.get("miktar", 0) or 0
            brut_tutar = urun.get("tutar", 0) or 0
            oran = urun.get("oran", 0) or 0
            kk_ksm = round(brut_tutar * kk_orani, 2)
            yaz_satir(row, evrak_tarihi, evrak_no, ua, miktar, brut_tutar, oran, kk_ksm)
            for ci, val in enumerate(row):
                ws.cell(row=ri, column=ci + 1, value=val).border = thin_border
            ri += 1

    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
