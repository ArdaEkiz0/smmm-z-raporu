FROM python:3.11-slim

# Sistem bağımlılıklarını tek katmanda yükle (image boyutunu küçültmek için --no-install-recommends)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-tur \
    libgl1 \
    libglib2.0-0 \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Önce requirements - Docker layer cache için (kod değişince pip install yeniden çalışmasın)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sonra uygulama kodunu kopyala
COPY . .

# EasyOCR modelini build sırasında indir (~100MB) - cold start'ı hızlandırır.
# Model indirilemezse build yine de başarılı olsun.
RUN python -c "import easyocr; easyocr.Reader(['tr', 'en'], gpu=False, verbose=False)" || true

# Streamlit config
RUN mkdir -p /app/.streamlit && \
    echo "[server]" > /app/.streamlit/config.toml && \
    echo "headless = true" >> /app/.streamlit/config.toml && \
    echo "runOnSave = false" >> /app/.streamlit/config.toml && \
    echo "enableCORS = false" >> /app/.streamlit/config.toml && \
    echo "enableXsrfProtection = false" >> /app/.streamlit/config.toml && \
    echo "maxUploadSize = 25" >> /app/.streamlit/config.toml && \
    echo "[browser]" >> /app/.streamlit/config.toml && \
    echo "gatherUsageStats = false" >> /app/.streamlit/config.toml && \
    echo "[client]" >> /app/.streamlit/config.toml && \
    echo "caching = true" >> /app/.streamlit/config.toml && \
    echo "showErrorDetails = false" >> /app/.streamlit/config.toml && \
    echo "toolbarMode = \"minimal\"" >> /app/.streamlit/config.toml && \
    echo "[global]" >> /app/.streamlit/config.toml && \
    echo "developmentMode = false" >> /app/.streamlit/config.toml

EXPOSE 8080

# Container başlangıcında:
#  1) Cloudflare cache purge (yeni deploy için)
#  2) EasyOCR/Tesseract warm-up - ilk istek gelmeden modeli belleğe yükle
#  3) Streamlit'i başlat
CMD ["sh", "-c", "python cache_purge.py 2>/dev/null; python -c 'from ocr import _get_easyocr; _ = _get_easyocr()' 2>/dev/null; streamlit run app.py --server.port=8080 --server.headless=true --server.address=0.0.0.0 --server.maxUploadSize=25 --browser.gatherUsageStats=false"]
