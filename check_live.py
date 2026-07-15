"""
Render'daki CANLI kodun icindeki fonksiyonu dogrudan calistir.
Eger kod eskiyse, hatali sonuc verir. Yeni ise dogrudur.
"""
import urllib.request
import json

# Render'dan bir test istegi yapalim - bir fiis isle ve sonucu gorelim
# Streamlit uzerinden dogrudan OCR calistirmak zor, ama bir health check yapalim
try:
    r = urllib.request.urlopen("https://smmm-z-raporu.onrender.com/_stcore/health", timeout=10)
    print("Health:", r.read().decode())
except Exception as e:
    print("Health error:", e)

# Simdi canli sayfanin HTML'ini cek ve versiyon kontrolu yap
try:
    r = urllib.request.urlopen("https://smmm-z-raporu.onrender.com/?smmm_auth=1", timeout=10)
    html = r.read().decode("utf-8")
    if "v3.0-OCR-NUCLEAR" in html:
        print("OK: Sayfada v3.0-OCR-NUCLEAR VAR")
    elif "v2.7" in html:
        print("HATA: Sayfada v2.7 var (eski)")
    else:
        print("BILINMIYOR: Versiyon banner bulunamadi")
        # v3.0'i ariyoruz
        if "v3.0" in html:
            print("v3.0 banner VAR")
        else:
            print("v3.0 banner YOK")
            # Butun 'v' ile baslayan stringleri ariyoruz
            import re
            matches = re.findall(r'v[\d.]+[A-Z-]*', html[:5000])
            print("Bulunan v* ifadeleri:", set(matches))
except Exception as e:
    print("Sayfa hatasi:", e)
