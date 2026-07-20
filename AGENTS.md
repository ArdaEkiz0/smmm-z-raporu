# SMMM Z Raporu - Proje Durumu

## Son Commit
`80b7f14` - fix: LUCA satir uretiminde bakiye hatasi giderildi (pushed to main)

## Çalışan Testler
- `test_app.py` - 13/13 PASS (birim testler)
- `test_luca_export.py` - 6/6 PASS

## Ortam
- **Streamlit UI** - `app.py`, port 8501
- **OCR** - Tesseract + EasyOCR hibrit (`ocr.py`)
- **LUCA Export** - `luca.py` (Excel çıktısı)
- **Veritabanı** - JSON tabanlı (`ogrenme_db.json`, `urun_kodlari.json`, `hesap_kodlari.json`)

## Bilinen Sorunlar
- `test_ocr_simulasyon.py` / `test_all_receipts.py` - `cv2` ve `streamlit` bağımlılıkları bu ortamda yok, Docker/venv'de çalışır
- `crash_log.txt` - `URUN_KODLARI_FILE` hatası (config.py'de tanımlı, eski crash)

## Önemli Dosyalar
- `luca.py` - LUCA/Logo/Netsis için muhasebe satırı üretimi
- `app.py` - Streamlit ana uygulama
- `ocr.py` - OCR motoru (Tesseract + EasyOCR)
- `config.py` - Yapılandırma
- `pages.py` - Streamlit sayfaları
- `utils.py` - Yardımcı fonksiyonlar

## Deploy
- Render: `render.yaml`
- Docker: `Dockerfile`
- Cloudflare Tunnel: `cloudflared.exe` + `baslat_tunnel.ps1`
