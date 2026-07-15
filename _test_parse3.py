"""TOPLAM debug."""
import re

OCR_TEXT = """TOPLAM ZI *17.864,90
TOPKDV ZI *176,91
TOPLAM ZO *1.987,00
TOPKDV ZO *@,00
TOPLAM *19.851,90
TOPKDV *176,91
KUM. TOPLAM *17.384.143,12
KUM. TOPKDV *657.603,18
"""

t_duz = " ".join(OCR_TEXT.split())
print(f"T_duz: {repr(t_duz)}")
print()

# Tum TOPLAM eslesmeleri
for i, m in enumerate(re.finditer(r'\bTOPLAM\s+([\d.,]+)', t_duz, re.IGNORECASE)):
    start = m.start()
    end = m.end()
    prefix = t_duz[max(0, start-25):start].upper()
    print(f"#{i}: '{m.group(0)}' at [{start}:{end}]")
    print(f"   prefix: '{prefix}'")
    print(f"   prefix[-6:]: '{prefix[-6:]}'")
    if re.search(r'K(ÜM|UM|UUM|ÜUM)\b', prefix):
        print(f"   -> KUM filtresi ATLAYACAK (regex: K(ÜM|UM|UUM|ÜUM)\\b)")
    if 'KÜM' in prefix[-6:]:
        print(f"   -> KÜM substring filtresi ATLAYACAK")
    if 'KUM.' in prefix[-6:]:
        print(f"   -> KUM. substring filtresi ATLAYACAK")
    print()
