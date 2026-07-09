"""OCR simulation: test full pipeline with realistic Z report text"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import parse_z_raporu, data_to_luca_rows, varsayilan_kodlar, urun_kodlari_varsayilan, generate_excel

ocr_cases = [
    {
        "name": "Market Z (1, 10 KDV)",
        "text": """
Z RAPORU
Tarih: 15.06.2026  Saat: 14:30
Fis No: 0042  Z No: 0150
EKMEK           %1      50    505,00
SUT             %10     20    220,00
YOGURT          %10     15    165,00
Brut * 890,00
Net Ciro * 890,00
NAKIT         5  * 500,00
Kredi Karti   10 * 200,00
Yemek Ceki    3  * 190,00
FIS IPTAL     2  *  50,00
TOPLAM       %1   * 500,00   TOPKDV * 5,00
TOPLAM       %10  * 350,00   TOPKDV * 35,00
"""
    },
    {
        "name": "Sadece nakit",
        "text": """
Z RAPORU
Tarih: 10.06.2026
Z No: 300
Brut * 1000,00
Net Ciro * 1000,00
NAKIT * 1000,00
"""
    },
    {
        "name": "KDV 20 + iade",
        "text": """
Z RAPORU
Tarih: 20.06.2026
Z No: 500
Brut * 5000,00
Net Ciro * 4500,00
Kredi Karti 5 * 4000,00
Nakit * 1000,00
FIS IPTAL 1 * 500,00
TOPLAM %20 * 5000,00 TOPKDV * 1000,00
"""
    },
    {
        "name": "Yemek ceki + KK + Nakit",
        "text": """
Z RAPORU
Tarih: 25.06.2026
Z No: 600
Brut * 3200,00
Net Ciro * 3200,00
NAKIT * 1000,00
Kredi Karti * 1500,00
Yemek Ceki * 700,00
"""
    },
]

kodlar = varsayilan_kodlar()
urun_kodlari = urun_kodlari_varsayilan()
ok = 0
for case in ocr_cases:
    r = parse_z_raporu(case["text"])
    assert r["tarih"] is not None, f'{case["name"]}: tarih None'
    rows = data_to_luca_rows(r, kodlar, 1, urun_kodlari)
    if rows:
        excel = generate_excel(rows)
        assert len(excel) > 0
    borc = sum(ro.get("Borç", 0) or 0 for ro in rows)
    alacak = sum(ro.get("Alacak", 0) or 0 for ro in rows)
    assert abs(borc - alacak) < 0.01, f'{case["name"]}: B={borc:.2f} A={alacak:.2f}'
    ok += 1
    print(f'  [PASS] {case["name"]} (B={borc:.2f}, A={alacak:.2f}, {len(rows)} satir)')

print(f"\nOCR simulasyon: {ok}/{len(ocr_cases)} basarili")

# Test with urun_kodlari matching
print("\n--- Urun Kodu match testi ---")
urun_kodlari2 = [
    {"pattern": "EKMEK", "hesap_kodu": "600.06", "aciklama": "Ekmek Satisi"},
    {"pattern": "SUT", "hesap_kodu": "600.07", "aciklama": "Sut Satisi"},
]
r2 = parse_z_raporu(ocr_cases[0]["text"])
rows2 = data_to_luca_rows(r2, kodlar, 1, urun_kodlari2)
ekmek_rows = [ro for ro in rows2 if ro["Hesap Kodu"] == "600.06"]
sut_rows = [ro for ro in rows2 if ro["Hesap Kodu"] == "600.07"]
assert len(ekmek_rows) == 1, f"Ekmek satiri yok: {[ro['Hesap Kodu'] for ro in rows2]}"
assert len(sut_rows) == 1, f"Sut satiri yok: {[ro['Hesap Kodu'] for ro in rows2]}"
print(f'  [PASS] Ekmek 600.06: Alacak={ekmek_rows[0]["Alacak"]:.2f}')
print(f'  [PASS] Sut 600.07: Alacak={sut_rows[0]["Alacak"]:.2f}')
b2 = sum(ro.get("Borç", 0) or 0 for ro in rows2)
a2 = sum(ro.get("Alacak", 0) or 0 for ro in rows2)
assert abs(b2 - a2) < 0.01, f"Balance: B={b2} A={a2}"
print(f'  [PASS] Balance: B={b2:.2f} A={a2:.2f}')
