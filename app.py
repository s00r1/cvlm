import os
import uuid
import shutil
import tempfile
from datetime import datetime

from flask import Flask, render_template, request, send_from_directory, redirect
import pdfkit
from docx import Document
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import docx2txt
import requests
import markdown2

# --- Configuration
UPLOAD_FOLDER = "tmp"
ALLOWED_EXTENSIONS = {"pdf", "docx"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# --- IA GROQ CONFIG (à adapter si besoin)
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# -- Extraction CV fichier (PDF/DOCX) avec OCR fallback
def extract_text_from_cv(file_path):
    ext = file_path.lower().split(".")[-1]
    text = ""
    if ext == "pdf":
        try:
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text()
            doc.close()
        except Exception:
            text = ""
        # OCR Fallback si pas de texte
        if not text.strip():
            doc = fitz.open(file_path)
            for page in doc:
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text += pytesseract.image_to_string(img, lang="fra+eng")
            doc.close()
    elif ext == "docx":
        try:
            text = docx2txt.process(file_path)
        except Exception:
            text = ""
    return text.strip()

# --- Appel IA GROQ pour extraction structurée et génération
def groq_extract_and_generate(prompt, max_tokens=2048):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    r = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# --- Prompt Extraction CV (double prompt, le plus structuré possible)
PROMPT_CV_EXTRACTION = """
Tu es un assistant RH. Reçois le texte d'un CV et retourne uniquement un JSON structuré ainsi :
{
  "nom": "...",
  "prenom": "...",
  "adresse": "...",
  "telephone": "...",
  "email": "...",
  "age": "...",
  "profil": "...",
  "competences": ["...", "..."],
  "experiences": ["...", "..."],
  "formations": ["...", "..."],
  "autres": ["..."]
}
Remplis chaque champ si tu as l’info, sinon mets une chaîne vide ou une liste vide.
N’invente rien. 
Voici le texte du CV :
---
"""

# --- Prompt Extraction Offre/LM/Fiche
PROMPT_EXTRACTION_OFFRE = """
Tu es un assistant RH intelligent. À partir d’une offre d’emploi ET d’un CV structuré (format JSON), retourne 3 blocs JSON :
- "fiche": (infos structurées de la fiche de poste, voir exemple)
- "cv": (proposition de CV adapté, voir exemple)
- "lettre_motivation": (texte d’une lettre de motivation personnalisée pour l’offre, très bien rédigée)
Ne réponds que par du JSON avec ces 3 clés, ne mets pas d’explications autour. Remplis au maximum chaque bloc.
Exemple :
{
"fiche": {
  "titre": "...", "employeur": "...", "ville": "...", "salaire": "...", "type_contrat": "...",
  "missions": ["..."], "competences": ["..."], "avantages": ["..."], "savoir_etre": ["..."], "autres": ["..."]
},
"cv": {
  "profil": "...",
  "competences": ["..."], "experiences": ["..."], "formations": ["..."], "autres": ["..."]
},
"lettre_motivation": "..."
}
Voici l’offre d’emploi (entre balises <offre>) et le CV candidat (entre balises <cv>) :
<offre>
{offre}
</offre>
<cv>
{cv_json}
</cv>
"""

# --- ROUTES

@app.route("/", methods=["GET", "POST"])
def index():
    error = ""
    fiche = cv = lettre_motivation = None
    values = {
        "nom": "", "prenom": "", "adresse": "",
        "telephone": "", "email": "", "age": "",
        "experiences": [], "diplomes": []
    }
    if request.method == "POST":
        # Gestion de l’upload de CV fichier
        cv_file = request.files.get("cv_file")
        offre = request.form.get("offre") or ""
        for k in ["nom", "prenom", "adresse", "telephone", "email", "age"]:
            values[k] = request.form.get(k, "").strip()
        # Expériences pro (array)
        experiences = []
        i = 0
        while True:
            poste = request.form.get(f"exp_poste_{i}", "")
            entreprise = request.form.get(f"exp_entreprise_{i}", "")
            ville = request.form.get(f"exp_ville_{i}", "")
            debut = request.form.get(f"exp_debut_{i}", "")
            fin = request.form.get(f"exp_fin_{i}", "")
            if poste or entreprise:
                experiences.append(f"{poste} chez {entreprise}, {ville} ({debut} - {fin})")
                i += 1
            else:
                break
        # Diplômes (array)
        diplomes = []
        i = 0
        while True:
            diplome = request.form.get(f"diplome_{i}", "")
            ecole = request.form.get(f"ecole_{i}", "")
            annee = request.form.get(f"annee_{i}", "")
            if diplome or ecole:
                diplomes.append(f"{diplome} - {ecole} ({annee})")
                i += 1
            else:
                break

        # Extraction du CV (upload ou manuel)
        cv_data = {
            "nom": values["nom"], "prenom": values["prenom"], "adresse": values["adresse"],
            "telephone": values["telephone"], "email": values["email"], "age": values["age"],
            "profil": "",
            "competences": [],
            "experiences": experiences,
            "formations": diplomes,
            "autres": []
        }
        if cv_file and allowed_file(cv_file.filename):
            filename = f"{uuid.uuid4().hex}.{cv_file.filename.rsplit('.', 1)[1].lower()}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            cv_file.save(file_path)
            # Extraction texte + IA
            try:
                texte_cv = extract_text_from_cv(file_path)
                if texte_cv:
                    prompt = PROMPT_CV_EXTRACTION + texte_cv
                    out = groq_extract_and_generate(prompt)
                    import json
                    cv_data = json.loads(out)
            except Exception:
                error = "CV non lisible, vérifiez votre fichier (essayez .docx si besoin)."
            finally:
                try:
                    os.remove(file_path)
                except Exception:
                    pass
        elif not any([values["nom"], values["prenom"], values["adresse"], values["telephone"], values["email"], values["age"], experiences, diplomes]):
            error = "Veuillez remplir au moins une expérience professionnelle, un diplôme, ou uploader votre CV."
            return render_template("index.html", error=error, **values)

        # Génération IA finale pour fiche / cv / lettre
        try:
            import json
            prompt = PROMPT_EXTRACTION_OFFRE.format(offre=offre, cv_json=json.dumps(cv_data, ensure_ascii=False))
            ia_json = groq_extract_and_generate(prompt, max_tokens=3072)
            struct = json.loads(ia_json)
            fiche = struct.get("fiche", {})
            cv = struct.get("cv", {})
            lettre_motivation = struct.get("lettre_motivation", "")
        except Exception as e:
            error = f"Erreur IA ou parsing JSON : {e}"
            return render_template("index.html", error=error, **values)

        # Stockage fichiers générés (PDF, DOCX)
        # Fichier temporaire unique
        suffix = uuid.uuid4().hex
        # Génération PDF CV
        from jinja2 import Template
        from flask import Markup

        date_du_jour = datetime.now().strftime("%d/%m/%Y")
        cv_html = render_template("cv_template.html", nom=cv_data["nom"], prenom=cv_data["prenom"], adresse=cv_data["adresse"],
                                 telephone=cv_data["telephone"], email=cv_data["email"], age=cv_data["age"],
                                 cv=cv, date_du_jour=date_du_jour)
        cv_pdf_file = f"cv_{suffix}.pdf"
        pdfkit.from_string(cv_html, os.path.join(UPLOAD_FOLDER, cv_pdf_file))
        # Lettre de motivation
        lm_html = render_template("lm_template.html", nom=cv_data["nom"], prenom=cv_data["prenom"], adresse=cv_data["adresse"],
                                  telephone=cv_data["telephone"], email=cv_data["email"], age=cv_data["age"],
                                  lettre_motivation=lettre_motivation, date_du_jour=date_du_jour)
        lm_pdf_file = f"lm_{suffix}.pdf"
        pdfkit.from_string(lm_html, os.path.join(UPLOAD_FOLDER, lm_pdf_file))
        # Fiche de poste
        fiche_html = render_template("fiche_poste_template.html", fiche=fiche, date_du_jour=date_du_jour)
        fiche_pdf_file = f"fiche_{suffix}.pdf"
        pdfkit.from_string(fiche_html, os.path.join(UPLOAD_FOLDER, fiche_pdf_file))
        # DOCX (CV, LM, FICHE) — ultra simple (bonus)
        def save_docx(content, filename):
            doc = Document()
            if isinstance(content, str):
                doc.add_paragraph(content)
            else:
                for k, v in content.items():
                    doc.add_heading(k, 1)
                    if isinstance(v, list):
                        for e in v:
                            doc.add_paragraph(str(e))
                    else:
                        doc.add_paragraph(str(v))
            doc.save(os.path.join(UPLOAD_FOLDER, filename))
        save_docx(cv, f"cv_{suffix}.docx")
        save_docx({"Lettre de motivation": lettre_motivation}, f"lm_{suffix}.docx")
        save_docx(fiche, f"fiche_{suffix}.docx")

        return render_template("result.html",
                               cv_file= f"cv_{suffix}.pdf", cv_file_docx= f"cv_{suffix}.docx",
                               lm_file= f"lm_{suffix}.pdf", lm_file_docx= f"lm_{suffix}.docx",
                               fiche_file= f"fiche_{suffix}.pdf", fiche_file_docx= f"fiche_{suffix}.docx",
                               nom=cv_data["nom"], prenom=cv_data["prenom"], adresse=cv_data["adresse"],
                               telephone=cv_data["telephone"], email=cv_data["email"], age=cv_data["age"],
                               cv=cv, fiche=fiche, lettre_motivation=lettre_motivation,
                               date_du_jour=date_du_jour
        )
    return render_template("index.html", error=error, **values)

@app.route("/download/<path:filename>")
def download(filename):
    # Download sécurisé (uniquement fichiers du dossier tmp)
    if not filename or "/" in filename or ".." in filename:
        return "Fichier invalide.", 400
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
