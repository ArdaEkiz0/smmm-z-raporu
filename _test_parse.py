"""OCR ciktisi uzerinde parse_z_raporu testi."""
import re
import sys
sys.path.insert(0, r'C:\Users\ozel\OneDrive\Masaüstü\luuaaaaaaaaaaa')

with open(r'C:\Users\ozel\OneDrive\Masaüstü\luuaaaaaaaaaaa\_ocr_test.txt', encoding="utf-8") as f:
    text = f.read()

t = text
for kesici in ["*** RAPOR SONU ***", "*** BELGEYİ SAKLAYINIZ ***", "*** BELGEYI SAKLAYINIZ ***", "RAPOR SONU"]:
    idx = t.upper().find(kesici.upper())
    if idx > 0:
        t = t[:idx]
        break
t_duz = " ".join(t.split())
print("=" * 60)
print("OCR TEXT (temizlenmis):")
print("=" * 60)
print(t_duz)
print()

# Brut
m = re.search(r'Br[uü]t\s+\*?\s*([\d.,]+)', t_duz, re.IGNORECASE)
print(f"Brut: {'VAR: ' + m.group(1) if m else 'YOK'}")

# Toplam (KUM olmayan)
toplam_match = None
for m in re.finditer(r'\bTOPLAM\s+([\d.,]+)', t_duz, re.IGNORECASE):
    start = m.start()
    prefix = t_duz[max(0, start-25):start].upper()
    if re.search(r'K[ÜÜUÜM]', prefix):
        continue
    toplam_match = m
    break
print(f"Toplam (Brut/Net): {'VAR: ' + toplam_match.group(1) if toplam_match else 'YOK'}")

# TopKDV
topkdv_match = None
for m in re.finditer(r'\bTOPKDV\s+([\d.,]+)', t_duz, re.IGNORECASE):
    start = m.start()
    prefix = t_duz[max(0, start-25):start].upper()
    if re.search(r'K[ÜÜUÜM]', prefix):
        continue
    topkdv_match = m
    break
print(f"TopKDV: {'VAR: ' + topkdv_match.group(1) if topkdv_match else 'YOK'}")

# Nakit
nakit_patterns = [
    r'NAK[İiI]T\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
    r'NAKIT\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
    r'[Nn]akit\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
    r'NAK[İiI]T\s+\*?\+?\s*([\d.,]+)',
    r'NAKIT\s+\*?\+?\s*([\d.,]+)',
]
print("Nakit denemeleri:")
for pat in nakit_patterns:
    nakit = re.search(pat, t_duz, re.IGNORECASE)
    if nakit:
        print(f"  ESLESEN: {pat} -> {nakit.groups()}")

# K.Karti
kart_patterns = [
    r'[Kk]\.?\s*[Kk]art[iıI]\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
    r'KART[Iİ]\s+(\d+)\s+\*?\+?\s*([\d.,]+)',
    r'KARTI\s+\*?\+?\s*([\d.,]+)',
    r'KART\s+\*?\+?\s*([\d.,]+)',
]
print("K.Karti denemeleri:")
for pat in kart_patterns:
    kart = re.search(pat, t_duz, re.IGNORECASE)
    if kart:
        print(f"  ESLESEN: {pat} -> {kart.groups()}")

# Iade (IPTAL)
iade_patterns = [
    r'Fi?s\s+[Ff]?[İiI]ptal\s+\d+\s*\*?\s*([\d.,]+)',
    r'(?:FPTAL|İPTAL|IPTAL|fptal|iptal)\s+\d+\s*\*?\s*([\d.,]+)',
    r'F[Iİ]S\s+İPTAL\s+\d+\s*\*?\s*([\d.,]+)',
    r'F[Iİ]S\s+IPTAL\s+\d+\s*\*?\s*([\d.,]+)',
    r'Fiş\s+İptal\s+\d+\s*\*?\s*([\d.,]+)',
    r'F[Iİ]S\s+İPTAL\s*\*?\s*([\d.,]+)',
    r'F[Iİ]S\s+IPTAL\s*\*?\s*([\d.,]+)',
    r'Fiş\s+İptal\s*\*?\s*([\d.,]+)',
]
print("Iade denemeleri:")
for pat in iade_patterns:
    iade = re.search(pat, t_duz, re.IGNORECASE)
    if iade:
        print(f"  ESLESEN: {pat} -> {iade.groups()}")
