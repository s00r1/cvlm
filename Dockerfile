# Image de base : Python 3.12 slim (plus rapide)
FROM python:3.12-slim

# Mise à jour des paquets système & installation de wkhtmltopdf + dépendances
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    poppler-utils \
    tesseract-ocr \
    build-essential \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    libfreetype6 \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Copier le code du projet
WORKDIR /app
COPY . .

# Installer les dépendances Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Exposer le port utilisé par Flask
EXPOSE 5000

# Commande de lancement de l'app Flask (Railway détecte ce CMD)
CMD ["python", "app.py"]
