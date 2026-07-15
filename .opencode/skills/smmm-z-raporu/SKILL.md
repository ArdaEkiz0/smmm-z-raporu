---
name: smmm-z-raporu
description: >
  SMMM Z Raporu Sistemi. Streamlit + Tesseract OCR tabanlı fiş okuma,
  LUCA/Logo/Netsis export, Bilanço/Serbest Meslek desteği. Kullanıcı Özel.
  Bu skill'i kullanıcının SMMM uygulaması ile ilgili her görevde aktif et.
---

# SMMM Z Raporu Sistemi

## Core Bilgiler
- **Proje:** `C:\Users\ozel\OneDrive\Masaüstü\luuaaaaaaaaaaa`
- **Ana dosya:** `app.py` (~3000 satır)
- **Çalıştırma:** `Baslat.bat` (hermes-agent venv ile streamlit, port 8501)
- **Dış erişim:** Cloudflare tunnel (port 8501, URL `cf_err.txt` içinde)
- **Python:** `C:\Users\ozel\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`

## OCR Pipeline
- Tesseract 5.5.0, `C:\Program Files\Tesseract-OCR`
- Türkçe dil verisi (`tur.traineddata`) yüklü
- Otsu + 2x upscale + Median + UnsharpMask + OEM 1 (LSTM)
- 3 threshold offset × 2 PSM = ~6 çağrı
- `ocr_image()` → `ocr_duzelt()` → `parse_z_raporu()` → `ogr_alanlari_uygula()`
- Tüm hatalar `crash_log.txt`'ye yazılır

## LUCA Export Formatı
- Excel 36 sütun
- cp1254 CSV, `;` delimiter
- `İŞLEM="1"`, `KATEGORİ="Defter Fişleri"`, `BELGE TÜRÜ="Z Raporu"`
- SİGARA KDV %0, KÜM.TOPLAM kullanılmaz

## Parse Sorunları (Geçmiş)
- TOPLAM/TOPKDV `*?` pattern, boşluklu sayılar, KUM prefix filtresi
- BURUT → BRÜT düzeltmesi (inline regex + sözlük + parse pattern)
- NET TUTAR pattern'i eklendi
- KREDİ KARTI ILE/BANKA KARTI pattern'leri eklendi
- Tüm pattern'lere `[:\-]?` (iki nokta üst üste) desteği eklendi

## Öğrenme Sistemi
- `duzeltme_sozlugu.json`: 40+ hazır OCR düzeltmesi
- `ogrenilen_sozluk.json`: Kullanıcıdan öğrenilen kelime düzeltmeleri
- `ogrenilen_alanlar.json`: Kullanıcıdan öğrenilen alan düzeltmeleri (firma/banka/tarih/Z No)
- Alan bazlı öğrenme: Boş VEYA çöp değerler otomatik doldurulur

## Kullanıcı Hatırlatmaları
- opencode eklentileri: `opencode-supermemory`, `opencode-wakatime`, `opencode-snip`, `@mohak34/opencode-notifier`, `opencode-skills-collection` kuruldu
- Yeni/faydalı bir opencode eklentisi görürsen kullanıcıya söyle

## Refactor Durumu
- Tüm sayfalar ayrı fonksiyonlara çıkarıldı (~1300 satır → 6 fonksiyon):
  - `_page_dashboard()` — Genel Bakış
  - `_page_z_raporu_yukle(hesap_kodlari)` — Z Raporu Yükle (~470 satır)
  - `_page_fis_gecmisi(hesap_kodlari)` — Fiş Geçmişi
  - `_page_mukellef_yonetimi()` — Mükellef Yönetimi
  - `_page_kdv_ozeti(hesap_kodlari)` — KDV Özeti
  - `_page_ayarlar()` — Ayarlar
- `hesapla_luca_rows()` modül seviyesine çıkarıldı
- `_mukellef_eslestir()` modül seviyesine çıkarıldı, `ml` parametresi eklendi
- duplicate nested `turkce_normalize` silindi
- Nakit regex pattern'leri yeniden sıralandı: boşluklu sayılar ("NAKIT 1 234,56") artık doğru parse ediliyor
- Uzun satır fix: `kdv_satirlar +=` multi-line f-string ile bölündü

## Önemli Dosyalar
- `app.py` - Ana uygulama (~3000 satır)
- `duzeltme_sozlugu.json` - OCR düzeltme sözlüğü
- `ogrenilen_sozluk.json` - Öğrenilen kelime düzeltmeleri
- `hesap_kodlari.json` - Hesap kodları
- `mukellefler.json` - Mükellef listesi
- `urun_kodlari.json` - Ürün kodları
- `Baslat.bat` - Başlatma scripti
- `crash_log.txt` - Hata logları
- `cf_err.txt` - Cloudflare tunnel URL
