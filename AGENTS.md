# SMMM Z Raporu - Proje Durumu

## Son Commit
`81ce8f9` - fix: test_eksik.py iade_kk assertion guncellendi (pushed to main)

## Çalışan Testler
- `test_app.py` - 13/13 PASS (birim testler)
- `test_luca_export.py` - 6/6 PASS
- `test_eksik.py` - 43/43 PASS
- `test_user_manager.py` - 20/20 PASS
- **Toplam: 123/123 PASS** (6 test dosyası)

## Ortam
- **Streamlit UI** - `app.py`, port 8501
- **OCR** - Tesseract + EasyOCR hibrit (`ocr.py`)
- **LUCA Export** - `luca.py` (Excel çıktısı)
- **Veritabanı** - JSON tabanlı (`ogrenme_db.json`, `urun_kodlari.json`, `hesap_kodlari.json`)
- **Model** - OpenCode, OmniRoute (`http://localhost:20128/v1`)

## LUCA Değişiklikleri (bu oturum)
- KDV hesabı: `kdv_kalemleri` > `urunler` (oran bazlı) > `brut - net_toplam`
- İade her durumda `_iade_dagit` ile KK → nakit → yemek sırasıyla dağıtılıyor
- `610.01` İade artık her zaman borç satırı olarak ekleniyor
- `iade_ayri` değişkeni kaldırıldı (dead code)

## CI/CD
- GitHub Actions: `ci.yml` (push/main'de test + lint)
- Render: `render.yaml` (Docker, auto-deploy)
- Docker: `Dockerfile` (Tesseract + EasyOCR)
- Keep-awake: Her 4 saatte bir uyku önleme

## Bilinen Sorunlar
- `test_ocr_simulasyonu.py` / `test_all_receipts.py` / `test_hibrit.py` - `cv2` ve `streamlit` bağımlılıkları bu ortamda yok, Docker/venv'de çalışır
- `crash_log.txt` - `URUN_KODLARI_FILE` hatası (config.py'de tanımlı, eski crash)
- `ogrenme_db.json` - Runtime değişiklikleri her commit'de ayrı ayıklanmalı

## Önemli Dosyalar
- `luca.py` - LUCA/Logo/Netsis için muhasebe satırı üretimi
- `app.py` - Streamlit ana uygulama (port 8501)
- `ocr.py` - OCR motoru (Tesseract + EasyOCR hibrit)
- `config.py` - Yapılandırma
- `pages.py` - Streamlit sayfaları
- `utils.py` - Yardımcı fonksiyonlar
- `user_manager.py` - Kullanıcı yönetimi (auth)

## Deploy
- Render: `render.yaml` (manuel CF_API_TOKEN + CF_ZONE_ID gerekli)
- Docker: `Dockerfile`
- Cloudflare Tunnel: `cloudflared.exe` + `baslat_tunnel.ps1`
