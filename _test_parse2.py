"""Yeni parse_z_raporu regex'lerini test et."""
import re

OCR_TEXT = """GOKKUSAGI MARKET
MIKAIL EKIZ ORTAKLIGI
30-06-2026 FIS NO: 44
Z NO: 2.124
T.GIDA 35
*17.224,90
EKMEK 1
*640 , 00
SIGARA 6
*1.987,00
NAKIT 1
*5 000,00
K.KARTI 39
*14.851,90
FIS IPTAL 3
*1.955,00
GECERLI SATIS FISI 40
TOPLAM ZI *17.864,90
TOPKDV ZI *176,91
TOPLAM ZO *1.987,00
TOPKDV ZO *@,00
TOPLAM *19.851,90
TOPKDV *176,91
KUM. TOPLAM *17.384.143,12
KUM. TOPKDV *657.603,18
"""

t = OCR_TEXT
for kesici in ["*** RAPOR SONU ***", "*** BELGEYİ SAKLAYINIZ ***"]:
    idx = t.upper().find(kesici.upper())
    if idx > 0:
        t = t[:idx]
        break
t_duz = " ".join(t.split())

def parse_tutar(s):
    if not s: return 0.0
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
        return float(s)
    except (ValueError, TypeError):
        return 0.0

# Yeni toplam regex
sonuc = {"brut": 0, "net_toplam": 0, "toplam_kdv": 0, "nakit": 0, "kredi_karti": 0, "iadeler": 0}

# Toplam (KUM olmayan)
toplam_match = None
for m in re.finditer(r'\bTOPLAM\s*\*?\s*([\d.,]+)', t_duz, re.IGNORECASE):
    start = m.start()
    prefix = t_duz[max(0, start-25):start].upper()
    if re.search(r'K(ÜM|UM|UUM|ÜUM)\b', prefix) or 'KÜM' in prefix[-6:] or 'KUM.' in prefix[-6:]:
        print(f"  Atlandi (KUM prefix): {m.group(0)}")
        continue
    toplam_match = m
    break
if toplam_match:
    val = parse_tutar(toplam_match.group(1))
    if val > 0:
        sonuc["brut"] = val
        sonuc["net_toplam"] = val
        print(f"  TOPLAM: {val}")

# TopKDV
topkdv_match = None
for m in re.finditer(r'\bTOPKDV\s*\*?\s*([\d.,]+)', t_duz, re.IGNORECASE):
    start = m.start()
    prefix = t_duz[max(0, start-25):start].upper()
    if re.search(r'K(ÜM|UM|UUM|ÜUM)\b', prefix) or 'KÜM' in prefix[-6:] or 'KUM.' in prefix[-6:]:
        continue
    topkdv_match = m
    break
if topkdv_match:
    val = parse_tutar(topkdv_match.group(1))
    if val > 0:
        sonuc["toplam_kdv"] = val
        print(f"  TOPKDV: {val}")

# Nakit - yeni pattern
nakit_patterns = [
    r'NAK[İiI]T\s+\d+\s+\*?\+?\s*([\d][\d.,\s]*[\d.,])',
    r'NAKIT\s+\d+\s+\*?\+?\s*([\d][\d.,\s]*[\d.,])',
]
for pat in nakit_patterns:
    nakit = re.search(pat, t_duz, re.IGNORECASE)
    if nakit:
        tutar_str = nakit.group(1).replace(" ", "")
        val = parse_tutar(tutar_str)
        if val > 0:
            sonuc["nakit"] = val
            print(f"  NAKIT: {val} (eslesme: {nakit.group(0)[:60]})")
            break

# K.Karti - yeni pattern
kart_patterns = [
    r'[Kk]\.?\s*[Kk]art[iıI]\s+\d+\s+\*?\+?\s*([\d][\d.,\s]*[\d.,])',
    r'KREDI\s*KARTI\s+\d+\s+\*?\+?\s*([\d][\d.,\s]*[\d.,])',
]
for pat in kart_patterns:
    kart = re.search(pat, t_duz, re.IGNORECASE)
    if kart:
        tutar_str = kart.group(1).replace(" ", "")
        val = parse_tutar(tutar_str)
        if val > 0:
            sonuc["kredi_karti"] = val
            print(f"  K.KARTI: {val} (eslesme: {kart.group(0)[:60]})")
            break

# Iade - yeni pattern
iade_patterns = [
    r'F[Iİ]S\s+IPTAL\s+\d+\s*\*?\s*([\d][\d.,\s]*[\d.,])',
    r'F[Iİ]S\s+İPTAL\s+\d+\s*\*?\s*([\d][\d.,\s]*[\d.,])',
]
for pat in iade_patterns:
    iade = re.search(pat, t_duz, re.IGNORECASE)
    if iade:
        tutar_str = iade.group(1).replace(" ", "")
        val = parse_tutar(tutar_str)
        if val > 0:
            sonuc["iadeler"] = val
            print(f"  IPTAL: {val} (eslesme: {iade.group(0)[:60]})")
            break

print()
print("=" * 60)
print("SONUC:")
print("=" * 60)
for k, v in sonuc.items():
    print(f"  {k}: {v}")
