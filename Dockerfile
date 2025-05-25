FROM python:3.11-slim

RUN apt-get update && apt-get install -y \\
    wkhtmltopdf \\
    tesseract-ocr \\
    poppler-utils \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]
