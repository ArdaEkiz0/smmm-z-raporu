"""
SMMM Z Raporu - Periyodik Kod Analiz Rutini
Bu scripti çalıştırarak projenin durumunu kontrol edebilirsiniz:
    python analiz_rutin.py
"""

import subprocess
import json
import os
from datetime import datetime


def calistir(cmd):
    """Komutu çalıştır ve sonucu döndür."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return "ZAMAN ASIMI"
    except Exception as e:
        return f"HATA: {e}"


def test_analiz():
    """Testleri çalıştır."""
    print("\n" + "="*60)
    print("TEST ANALİZİ")
    print("="*60)
    cikti = calistir(
        r'"C:\Users\ozel\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m pytest test_app.py test_eksik.py -v --tb=short'
    )
    print(cikti)
    return "passed" in cikti and "failed" not in cikti


def syntax_kontrol():
    """Syntax hatalarını kontrol et."""
    print("\n" + "="*60)
    print("SYNTAX KONTROL")
    print("="*60)
    dosyalar = ["app.py", "ocr.py", "luca.py", "pages.py", "veritabani.py", "utils.py", "config.py"]
    hatalar = []
    for d in dosyalar:
        cikti = calistir(f'py -c "import py_compile; py_compile.compile(\'{d}\', doraise=True)"')
        if "HATA" in cikti or "SyntaxError" in cikti:
            hatalar.append(d)
            print(f"  HATA: {d}")
        else:
            print(f"  OK: {d}")
    return len(hatalar) == 0


def graphify_guncelle():
    """Graphify'ı güncelle."""
    print("\n" + "="*60)
    print("GRAPHIFY GÜNCELLEME")
    print("="*60)
    calistir(r'"C:\Users\ozel\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m graphify . --code-only --update')
    calistir(r'"C:\Users\ozel\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m graphify cluster-only .')
    
    # Vault'a kopyala
    vault = r"C:\Users\ozel\OneDrive\Masaüstü\smmm-vault\Proje"
    for f in ["graph.html", "graph.json", "GRAPH_REPORT.md"]:
        src = os.path.join("graphify-out", f)
        dst = os.path.join(vault, f)
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, dst)
            print(f"  {f} güncellendi")
    
    # Graph bilgilerini oku
    rapor = os.path.join("graphify-out", "GRAPH_REPORT.md")
    if os.path.exists(rapor):
        with open(rapor, "r", encoding="utf-8") as f:
            for satir in f.readlines()[:10]:
                print(f"  {satir.strip()}")


def dosya_istatistikleri():
    """Dosya boyutları ve satır sayıları."""
    print("\n" + "="*60)
    print("DOSYA İSTATİSTİKLERİ")
    print("="*60)
    dosyalar = ["app.py", "ocr.py", "luca.py", "pages.py", "veritabani.py", "utils.py", "config.py"]
    for d in dosyalar:
        if os.path.exists(d):
            with open(d, "r", encoding="utf-8") as f:
                satir = len(f.readlines())
            boyut = os.path.getsize(d)
            print(f"  {d}: {satir} satır, {boyut:,} byte")


def hata_ozeti():
    """Son hata loglarını kontrol et."""
    print("\n" + "="*60)
    print("HATA ÖZETİ")
    print("="*60)
    if os.path.exists("crash_log.txt"):
        with open("crash_log.txt", "r", encoding="utf-8") as f:
            icerik = f.read()
        if icerik.strip():
            satirlar = icerik.strip().split("\n")
            print(f"  Toplam {len(satirlar)} satır hata logu")
            print(f"  Son hata: {satirlar[-1][:100]}")
        else:
            print("  Hata logu boş")
    else:
        print("  crash_log.txt bulunamadı")


def main():
    print(f"SMMM Z Raporu Analiz - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("="*60)
    
    sonuclar = {}
    sonuclar["testler"] = test_analiz()
    sonuclar["syntax"] = syntax_kontrol()
    
    dosya_istatistikleri()
    hata_ozeti()
    graphify_guncelle()
    
    print("\n" + "="*60)
    print("ÖZET")
    print("="*60)
    print(f"  Testler: {'[OK] BASARILI' if sonuclar['testler'] else '[HATA] BASARISIZ'}")
    print(f"  Syntax: {'[OK] TEMIZ' if sonuclar['syntax'] else '[HATA] HATALI'}")
    print("="*60)


if __name__ == "__main__":
    main()
