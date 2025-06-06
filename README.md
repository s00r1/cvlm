# Générateur de CV & Lettre de Motivation

Webapp pour générer automatiquement un CV et une lettre de motivation à partir d'une offre d'emploi.
Technos : Python Flask, HTML/CSS, pdfkit + wkhtmltopdf pour la génération de PDF.

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
3. Installez également les paquets système nécessaires (``wkhtmltopdf`` est requis pour ``pdfkit``) :
   ```bash
   sudo apt-get install wkhtmltopdf poppler-utils tesseract-ocr
   ```
4. Définir la clé d'API Groq
   ```bash
   export GROQ_API_KEY=<votre_clef_groq>
   ```
5. Lancer l'application
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

## Fichiers temporaires

Les documents générés (PDF et DOCX) sont stockés dans le dossier `tmp/`. Lorsqu’un utilisateur télécharge un fichier via l’interface, celui-ci est aussitôt supprimé du dossier afin d’éviter son accumulation. L’application effectue également un nettoyage automatique au démarrage et après chaque requête pour supprimer les fichiers âgés de plus d’une heure. Vous pouvez néanmoins supprimer manuellement le reste du contenu de `tmp/` si nécessaire.

## Option Premium

L’interface propose un champ **Type de CV** pour choisir entre le modèle basique
ou le modèle *premium*. Ce dernier permet d’ajouter une photo de profil via un
champ de téléversement qui n’apparaît que lorsqu’« premium » est sélectionné.

La logique est contrôlée par la constante `PREMIUM_PHOTO_REQUIRED` définie dans
`app.py`. Sa valeur par défaut est `False` : une photo n’est donc pas
obligatoire et, si rien n’est fourni, une petite image blanche encodée en
base64 (`PREMIUM_PLACEHOLDER_B64`) est utilisée à la place. Vous pouvez modifier
cette valeur dans `app.py` pour rendre la photo strictement nécessaire.

## Tests

Les tests unitaires fournis n'utilisent pas l'API Groq. Ils peuvent donc être lancés sans définir la variable `GROQ_API_KEY` :

```bash
pytest
```

Les tests concernant l'extraction de texte utilisent `pytesseract` et `pdf2image`. Pour exécuter l'intégralité de la suite, assurez-vous que les dépendances système suivantes sont installées :

```bash
sudo apt-get install poppler-utils tesseract-ocr
```

Les bibliothèques Python correspondantes doivent aussi être présentes. Installez les paquets facultatifs `requests`, `pytesseract`, `pdf2image`, `python-docx`, `PyPDF2` et `reportlab` pour éviter l'échec des tests :

```bash
pip install requests pytesseract pdf2image python-docx PyPDF2 reportlab
```

Sans ces dépendances, tout ou partie de la suite `pytest` échouera.

## Linting

Le projet utilise `flake8` avec une limite de 88 caractères par ligne. Vous pouvez lancer la vérification locale avec :

```bash
flake8
```

Le pied de page de l'application affiche désormais automatiquement l'année en cours.
