# Générateur de CV & Lettre de Motivation

Webapp pour générer automatiquement un CV et une lettre de motivation à partir d'une offre d'emploi.  
Technos : Python Flask, HTML/CSS, WeasyPrint.

## Lancer en local

1. Optionnel : créer un environnement virtuel
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Installer les dépendances
   ```bash
   pip install -r requirements.txt
   ```
3. Définir la clé d'API Groq
   ```bash
   export GROQ_API_KEY=<votre_clef_groq>
   ```
4. Lancer l'application
   ```bash
   python app.py
   ```

La variable `GROQ_API_KEY` doit contenir la clé d'API Groq utilisée par
l'application pour générer les textes.

## Déploiement sur Railway

1. Créez un nouveau projet Railway et connectez ce dépôt Git.
2. Dans l'onglet *Variables*, ajoutez `GROQ_API_KEY` avec votre clé.
3. Lancez le déploiement ; Railway utilisera automatiquement le `Dockerfile`
   et la commande du `Procfile` (`python app.py`).

Pour un test local sans Docker, exécutez simplement la commande ci‑dessus
après avoir installé les dépendances et défini la variable `GROQ_API_KEY`.
