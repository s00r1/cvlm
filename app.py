from flask import Flask, render_template, request, send_file, url_for, redirect
from jinja2 import Template
import pdfkit
import os
import platform
import shutil
from docx import Document
import re
import requests
import time
import tempfile
import json
import uuid

import pytesseract
from pdf2image import convert_from_path
from PyPDF2 import PdfReader

# === Configuration IA GROQ ===
GROQ_API_KEY = "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"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

app = Flask(__name__)

DOWNLOAD_DIR = os.path.join(app.root_path, 'static', 'downloads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==================== UTILS ====================
def extract_text_from_pdf(file_path):
    try:
        reader = PdfReader(file_path)
        fulltext = "\n".join([page.extract_text() or "" for page in reader.pages])
        if fulltext.strip():
            return fulltext
    except Exception:
        pass
    try:
        images = convert_from_path(file_path)
        text = "\n".join([pytesseract.image_to_string(img, lang='fra+eng') for img in images])
        return text
    except Exception:
        return ""

def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception:
        return ""

def ask_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    data = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "Tu es un assistant RH expert, spécialiste du recrutement en France."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 2800
    }
    resp = requests.post(url, headers=headers, json=data, timeout=80)
    j = resp.json()
    content = j["choices"][0]["message"]["content"]
    return content

def extract_first_json(text):
    m = re.search(r'(\{[\s\S]+\})', text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        text_clean = m.group(1).replace('\n', '').replace('\r', '')
        try:
            return json.loads(text_clean)
        except Exception:
            return None

def find_wkhtmltopdf():
    path = shutil.which("wkhtmltopdf")
    return path

def generate_temp_filename(suffix):
    # Utilise le dossier downloads (persistance temporaire)
    return os.path.join(DOWNLOAD_DIR, uuid.uuid4().hex + suffix)

if platform.system() == "Windows":
    WKHTMLTOPDF_PATH = r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
else:
    wkhtmltopdf_path = find_wkhtmltopdf()
    if wkhtmltopdf_path:
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    else:
        raise RuntimeError("wkhtmltopdf non trouvé sur le système Railway ! Vérifie l'installation.")

@app.route('/', methods=['GET', 'POST'])
def index():
    context = {
        "nom": "", "prenom": "", "adresse": "", "telephone": "", "email": "", "age": "",
        "xp_poste": [], "xp_entreprise": [], "xp_lieu": [], "xp_debut": [], "xp_fin": [],
        "dip_titre": [], "dip_lieu": [], "dip_date": [],
        "description": "",
        "error": ""
    }

    if request.method == 'POST':
        error = ""
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        adresse = request.form.get('adresse', '').strip()
        telephone = request.form.get('telephone', '').strip()
        email = request.form.get('email', '').strip()
        age = request.form.get('age', '').strip()
        description = request.form.get('description', '').strip()
        xp_poste = request.form.getlist('xp_poste')
        xp_entreprise = request.form.getlist('xp_entreprise')
        xp_lieu = request.form.getlist('xp_lieu')
        xp_debut = request.form.getlist('xp_debut')
        xp_fin = request.form.getlist('xp_fin')
        dip_titre = request.form.getlist('dip_titre')
        dip_lieu = request.form.getlist('dip_lieu')
        dip_date = request.form.getlist('dip_date')
        cv_file = request.files.get('cv_file')

        context.update({
            "nom": nom, "prenom": prenom, "adresse": adresse, "telephone": telephone, "email": email, "age": age,
            "xp_poste": xp_poste, "xp_entreprise": xp_entreprise, "xp_lieu": xp_lieu, "xp_debut": xp_debut, "xp_fin": xp_fin,
            "dip_titre": dip_titre, "dip_lieu": dip_lieu, "dip_date": dip_date,
            "description": description
        })

        cv_uploaded_text = ""
        infos = {}

        if cv_file and cv_file.filename:
            ext = cv_file.filename.lower().split('.')[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix="." + ext) as tmp:
                cv_file.save(tmp.name)
                file_path = tmp.name
            if ext == "pdf":
                cv_uploaded_text = extract_text_from_pdf(file_path)
            elif ext == "docx":
                cv_uploaded_text = extract_text_from_docx(file_path)
            else:
                error = "Format de CV non supporté (PDF ou DOCX uniquement)"
                os.unlink(file_path)
                return render_template("index.html", error=error, **context)
            os.unlink(file_path)

            # Extraction auto des infos du CV
            prompt_extract_infos = f"""
Lis ce CV et extrait les informations personnelles si elles sont présentes, en remplissant ce JSON :

{{
  "nom": "",
  "prenom": "",
  "adresse": "",
  "telephone": "",
  "email": "",
  "age": ""
}}

CV :
\"\"\"
{cv_uploaded_text}
\"\"\"
"""
            infos_json = ask_groq(prompt_extract_infos)
            infos = extract_first_json(infos_json) or {}

            nom = infos.get("nom", "") or nom
            prenom = infos.get("prenom", "") or prenom
            adresse = infos.get("adresse", "") or adresse
            telephone = infos.get("telephone", "") or telephone
            email = infos.get("email", "") or email
            age = infos.get("age", "") or age

        fiche_poste = {}
        if cv_uploaded_text.strip():
            # Étape 1 : Extraction/structuration du CV (JSON)
            prompt_parse_cv = f"""
Lis attentivement le texte suivant extrait d’un CV PDF ou DOCX. Trie les informations dans ce JSON, section par section, sans jamais inventer :

{{
  "profil": "...",
  "competences": ["...", "..."],
  "experiences": ["...", "..."],
  "formations": ["...", "..."],
  "autres": ["...", "..."]
}}

Si tu ne trouves pas une section, laisse-la vide, mais structure toujours le JSON comme ci-dessus.

TEXTE DU CV À PARSER :
\"\"\"
{cv_uploaded_text}
\"\"\"
"""
            parsed_cv_json = ask_groq(prompt_parse_cv)
            cv_data = extract_first_json(parsed_cv_json)
            if not cv_data:
                error = "Erreur extraction IA du CV : JSON IA non extrait ou malformé."
                return render_template("index.html", error=error, **context)

            # Étape 2 : Adaptation à l’offre
            prompt_lm_cv = f"""
Voici le parsing structuré du CV du candidat, issu de l’étape précédente :
{json.dumps(cv_data, ensure_ascii=False, indent=2)}

Voici l'offre d'emploi à laquelle il postule :
\"\"\"
{description}
\"\"\"

1. Rédige une lettre de motivation personnalisée et professionnelle adaptée à l'offre et au parcours du candidat (exploite le maximum d’infos utiles, mets en avant les expériences ou compétences transversales si besoin).
2. Génère le contenu d’un CV adapté à l’offre, en sélectionnant :
   - Un paragraphe de profil synthétique (adapté au poste)
   - Les compétences les plus pertinentes (croisées entre CV et offre)
   - Les expériences professionnelles les plus adaptées, sous forme de bullet points (intitulé, entreprise, dates, mission principale)
   - Les formations principales
   - Autres infos utiles

Rends ce JSON strictement :
{{
  "lettre_motivation": "....",
  "cv_adapte": {{
    "profil": "...",
    "competences": ["...", "..."],
    "experiences": ["...", "..."],
    "formations": ["...", "..."],
    "autres": ["...", "..."]
  }}
}}
"""
            result2 = ask_groq(prompt_lm_cv)
            data2 = extract_first_json(result2)
            if not data2:
                error = "Erreur extraction IA LM/CV : JSON IA non extrait ou malformé."
                return render_template("index.html", error=error, **context)

            lettre_motivation = data2.get("lettre_motivation", "")
            cv_adapte = data2.get("cv_adapte", {})

            # Génération de la fiche de poste
            prompt_fiche_poste = f"""
Lis attentivement l'offre d'emploi suivante et extrait-en les éléments principaux pour générer une fiche de poste structurée, en remplissant strictement ce JSON (sans inventer) :

{{
  "titre": "...",
  "employeur": "...",
  "ville": "...",
  "salaire": "...",
  "type_contrat": "...",
  "missions": ["...", "..."],
  "competences": ["...", "..."],
  "avantages": ["...", "..."],
  "savoir_etre": ["...", "..."],
  "autres": ["..."]
}}

Offre à analyser :
\"\"\"
{description}
\"\"\"
"""
            fiche_poste_json = ask_groq(prompt_fiche_poste)
            fiche_poste = extract_first_json(fiche_poste_json) or {}

            # ====== GÉNÉRATION DES FICHIERS (PDF/DOCX) ======
            fiche_pdf_path = generate_temp_filename(".pdf")
            fiche_docx_path = generate_temp_filename(".docx")
            cv_pdf_path = generate_temp_filename(".pdf")
            cv_docx_path = generate_temp_filename(".docx")
            lm_pdf_path = generate_temp_filename(".pdf")
            lm_docx_path = generate_temp_filename(".docx")

            fiche_html = render_template("fiche_poste_template.html", fiche=fiche_poste)
            cv_html = render_template("cv_template.html", cv=cv_adapte, nom=nom, prenom=prenom, adresse=adresse, telephone=telephone, email=email, age=age)
            lm_html = render_template("lm_template.html", lettre_motivation=lettre_motivation, nom=nom, prenom=prenom, adresse=adresse, telephone=telephone, email=email, age=age)

            with open(fiche_pdf_path, "wb") as f: f.write(pdfkit.from_string(fiche_html, False, configuration=config))
            with open(cv_pdf_path, "wb") as f: f.write(pdfkit.from_string(cv_html, False, configuration=config))
            with open(lm_pdf_path, "wb") as f: f.write(pdfkit.from_string(lm_html, False, configuration=config))

            doc = Document()
            doc.add_heading(fiche_poste.get("titre", "Fiche de poste"), 0)
            for k,v in fiche_poste.items():
                if isinstance(v, list):
                    doc.add_heading(k.capitalize(), 1)
                    for elt in v: doc.add_paragraph(str(elt), style='List Bullet')
                elif isinstance(v, str) and v.strip():
                    doc.add_paragraph(f"{k.capitalize()} : {v}")
            doc.save(fiche_docx_path)

            doc2 = Document()
            doc2.add_heading(f"{prenom} {nom} — CV", 0)
            doc2.add_paragraph(cv_adapte.get("profil", ""))
            doc2.add_heading("Compétences", 1)
            for elt in cv_adapte.get("competences", []): doc2.add_paragraph(elt, style='List Bullet')
            doc2.add_heading("Expériences", 1)
            for elt in cv_adapte.get("experiences", []): doc2.add_paragraph(elt, style='List Bullet')
            doc2.add_heading("Formations", 1)
            for elt in cv_adapte.get("formations", []): doc2.add_paragraph(elt, style='List Bullet')
            doc2.save(cv_docx_path)

            doc3 = Document()
            doc3.add_heading("Lettre de motivation", 0)
            doc3.add_paragraph(lettre_motivation)
            doc3.save(lm_docx_path)

            return render_template("result.html",
                                   fiche_poste=fiche_poste,
                                   cv=cv_adapte,
                                   lettre_motivation=lettre_motivation,
                                   cv_uploaded_text=cv_uploaded_text,
                                   fiche_file=os.path.basename(fiche_pdf_path), fiche_file_docx=os.path.basename(fiche_docx_path),
                                   cv_file=os.path.basename(cv_pdf_path), cv_file_docx=os.path.basename(cv_docx_path),
                                   lm_file=os.path.basename(lm_pdf_path), lm_file_docx=os.path.basename(lm_docx_path),
                                   nom=nom, prenom=prenom, adresse=adresse, telephone=telephone, email=email, age=age
                                   )
        else:
            # Saisie manuelle (à compléter selon ta logique actuelle…)
            error = "Veuillez remplir au moins une expérience professionnelle, un diplôme, ou uploader votre CV."
            return render_template("index.html", error=error, **context)

    return render_template("index.html", **context)

@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return "Fichier introuvable", 404
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
