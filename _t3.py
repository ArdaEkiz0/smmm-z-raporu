import re
OCR = "TOPLAM ZI *17.864,90 TOPKDV ZI *176,91 TOPLAM ZO *1.987,00 TOPKDV ZO *@,00 TOPLAM *19.851,90 TOPKDV *176,91 KUM. TOPLAM *17.384.143,12 KUM. TOPKDV *657.603,18"
print("T_duz:", OCR)
print()
matches = list(re.finditer(r'\bTOPLAM\s+([\d.,]+)', OCR, re.IGNORECASE))
print(f"Bulunan: {len(matches)} TOPLAM")
for i, m in enumerate(matches):
    s = m.start()
    e = m.end()
    prefix = OCR[max(0, s-25):s].upper()
    print(f"#{i}: '{m.group(0)}' prefix='{prefix[-10:]}'", end=" ")
    skip = (re.search(r'K(ÜM|UM|UUM|ÜUM)\b', prefix) or 'KÜM' in prefix[-6:] or 'KUM.' in prefix[-6:])
    print(f"-> {'ATLA' if skip else 'AL'}")
