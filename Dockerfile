FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-tur \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# EasyOCR model dosyalarini onceden indir (ilk calistirmada bekleme olmasin)
RUN python -c "import easyocr; easyocr.Reader(['tr', 'en'], gpu=False, verbose=False)" || true

EXPOSE 8080
CMD ["sh", "-c", "python cache_purge.py 2>/dev/null; streamlit run app.py --server.port=8080 --server.headless=true --server.address=0.0.0.0"]
