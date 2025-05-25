import os
import shutil
import tempfile
import uuid
from datetime import datetime

from flask import Flask, render_template, request, send_file, redirect, url_for
from werkzeug.utils import secure_filename

import requests
import fitz  # PyMuPDF
import docx2txt
import pytesseract
from PIL import Image

# === CONFIGURATION ===

UPLOAD_FOLDER = "tmp"
ALLOWED_EXTENSIONS = {"pdf", "docx"}

GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# === UTILS ===

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        text = ""
    if text.strip():
        return text
    # OCR fallback
    try:
        doc = fitz.open(pdf_path)
        ocr_text = []
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text_ocr = pytesseract.image_to_string(img, lang="fra")
            ocr_text.append(text_ocr)
        doc.close()
        return "\n".join(ocr_text)
    except Exception as e:
        return ""
    return ""

def extract_text_from_docx(docx_path):
    try:
        return docx2txt.process(docx_path)
    except Exception as e:
        return ""

def save_temp_file(content_bytes, ext):
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, "wb") as f:
        f.write(content_bytes)
    return filename, filepath

def call_groq(prompt, max_tokens=1024, system_prompt=None):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    data = {
        "model": GROQ_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.45,
        "stream": False
    }
    r = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=60)
    if r.status_code == 200:
        content = r.json()["choices"][0]["message"]["content"]
        return content
    else:
        return f"Erreur IA : {r.status_code} {r.text}"

def parse_ia_json(text):
    import json
    try:
        return json.loads(text)
    except Exception as e:
        # Si l’IA répond avec du texte + JSON, tente d’isoler la partie JSON
        import re
        matches = re.findall(r'\{[\s\S]+\}', text)
        if matches:
            try:
                return json.loads(matches[0])
            except Exception:
                pass
        return None

# === ROUTES ===

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    context = {
        "nom": "",
        "prenom": "",
        "adresse": "",
        "telephone": "",
        "email": "",
        "age": "",
        "experiences": [],
        "diplomes": [],
        "offre": "",
        "cv_uploaded_text": "",
        "cv_filename": "",
        "fiche_file": "",
        "fiche_file_docx": "",
        "cv_file": "",
        "cv_file_docx": "",
        "lm_file": "",
        "lm_file_docx": ""
    }

    if request.method == 'POST':
        # --- Gestion de l’upload CV ---
        cv_uploaded_text = ""
        cv_filename = ""
        nom, prenom, adresse, telephone, email, age = "", "", "", "", "", ""
        experiences, diplomes = [], []
        if 'cv_file' in request.files and request.files['cv_file']:
            file = request.files['cv_file']
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = secure_filename(file.filename)
                tmp_name = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, tmp_name)
                file.save(filepath)
                cv_filename = tmp_name
                if ext == "pdf":
                    cv_uploaded_text = extract_text_from_pdf(filepath)
                elif ext == "docx":
                    cv_uploaded_text = extract_text_from_docx(filepath)
                else:
                    cv_uploaded_text = ""
            else:
                error = "Format de fichier non supporté."
        else:
            file = None

        # --- Si pas de CV uploadé, on prend les données du formulaire ---
        nom = request.form.get("nom", "")
        prenom = request.form.get("prenom", "")
        adresse = request.form.get("adresse", "")
        telephone = request.form.get("telephone", "")
        email = request.form.get("email", "")
        age = request.form.get("age", "")
        try:
            experiences = [
                {
                    "poste": request.form.getlist("poste[]")[i],
                    "entreprise": request.form.getlist("entreprise[]")[i],
                    "lieu": request.form.getlist("lieu[]")[i],
                    "date_debut": request.form.getlist("date_debut[]")[i],
                    "date_fin": request.form.getlist("date_fin[]")[i],
                }
                for i in range(len(request.form.getlist("poste[]")))
            ]
        except Exception:
            experiences = []
        try:
            diplomes = [
                {
                    "diplome": request.form.getlist("diplome[]")[i],
                    "date_obtention": request.form.getlist("date_obtention[]")[i],
                    "lieu_obtention": request.form.getlist("lieu_obtention[]")[i],
                }
                for i in range(len(request.form.getlist("diplome[]")))
            ]
        except Exception:
            diplomes = []
        offre = request.form.get("offre", "")

        # --- Condition d'accès : au moins CV OU une expérience OU un diplôme ---
        if not (cv_uploaded_text or experiences or diplomes):
            error = "Veuillez remplir au moins une expérience professionnelle, un diplôme, ou uploader votre CV"
            context.update(locals())
            context['error'] = error
            return render_template("index.html", **context)

        # --- Extraction/structuration via IA (double prompt) ---
        # (1) On structure tout ce qu'on a (uploadé ou saisi) pour préparer le prompt LM/CV
        base_infos = {
            "nom": nom, "prenom": prenom, "adresse": adresse, "telephone": telephone, "email": email, "age": age,
            "experiences": experiences, "diplomes": diplomes
        }
        if cv_uploaded_text:
            prompt_extract = f"""
Analyse ce texte extrait d'un CV utilisateur et retourne les informations structurées en JSON, sous ce format :
{{
  "nom": "...", "prenom": "...", "adresse": "...", "telephone": "...", "email": "...", "age": "...",
  "experiences": [{{"poste":"", "entreprise":"", "lieu":"", "date_debut":"", "date_fin":""}}],
  "diplomes": [{{"diplome":"", "date_obtention":"", "lieu_obtention":""}}],
  "competences": ["", ...]
}}
N'invente rien, remplis seulement ce que tu trouves clairement dans le texte !
Texte extrait du CV : 
{cv_uploaded_text}
"""
            ia_json = call_groq(prompt_extract, max_tokens=2048)
            ia_struct = parse_ia_json(ia_json)
            if ia_struct:
                # On met à jour les variables de base
                nom = ia_struct.get("nom", nom)
                prenom = ia_struct.get("prenom", prenom)
                adresse = ia_struct.get("adresse", adresse)
                telephone = ia_struct.get("telephone", telephone)
                email = ia_struct.get("email", email)
                age = ia_struct.get("age", age)
                experiences = ia_struct.get("experiences", experiences)
                diplomes = ia_struct.get("diplomes", diplomes)
                competences = ia_struct.get("competences", [])
            else:
                competences = []
        else:
            competences = []

        # (2) Préparation du prompt pour générer CV structuré, LM et fiche de poste
        prompt_cv = f"""
À partir de ces informations personnelles :
Nom : {nom}
Prénom : {prenom}
Adresse : {adresse}
Téléphone : {telephone}
Email : {email}
Âge : {age}

Expériences professionnelles :
{str(experiences)}

Diplômes :
{str(diplomes)}

Compétences (s’il y en a) :
{', '.join(competences) if competences else ""}

Et à partir de cette offre d’emploi :
{offre}

1. Génère un **CV structuré** en JSON (sections : profil, compétences, expériences, formations, autres)
2. Génère une **lettre de motivation** professionnelle, sur-mesure, qui “matche” le profil ci-dessus avec l’offre, valorise au mieux les compétences/expériences.
3. Génère une **fiche de poste** en JSON (titre, employeur, ville, salaire, type_contrat, missions, competences, avantages, savoir_etre, autres)
Retourne le tout dans un seul JSON comme :
{{
  "cv": {{
      "profil": "...", "competences": [...], "experiences": [...], "formations": [...], "autres": [...]
  }},
  "lettre_motivation": "...",
  "fiche_poste": {{
      "titre": "...", "employeur": "...", "ville": "...", "salaire": "...", "type_contrat": "...",
      "missions": [...], "competences": [...], "avantages": [...], "savoir_etre": [...], "autres": [...]
  }}
}}
N’invente rien : utilise uniquement les infos données.
Sois concis, professionnel, et structuré.
"""
        ia_json_2 = call_groq(prompt_cv, max_tokens=3072)
        results = parse_ia_json(ia_json_2)
        if not results:
            error = "Erreur IA ou parsing JSON : JSON IA non extrait ou malformé."
            context.update(locals())
            context['error'] = error
            return render_template("index.html", **context)

        # --- On récupère le contenu IA ---
        cv = results.get("cv", {})
        lettre_motivation = results.get("lettre_motivation", "")
        fiche_poste = results.get("fiche_poste", {})

        # --- Génération fichiers à télécharger ---
        from docx import Document
        import pdfkit

        # CV
        date_du_jour = datetime.now().strftime("%d/%m/%Y")
        # (1) HTML
        cv_html = render_template("cv_template.html", cv=cv, nom=nom, prenom=prenom, adresse=adresse, telephone=telephone, email=email, age=age, date_du_jour=date_du_jour)
        cv_filename_pdf = f"{uuid.uuid4().hex}.pdf"
        cv_filepath_pdf = os.path.join(UPLOAD_FOLDER, cv_filename_pdf)
        pdfkit.from_string(cv_html, cv_filepath_pdf)
        # (2) DOCX
        cv_filename_docx = f"{uuid.uuid4().hex}.docx"
        cv_filepath_docx = os.path.join(UPLOAD_FOLDER, cv_filename_docx)
        doc = Document()
        doc.add_heading(f"{prenom} {nom}", 0)
        doc.add_paragraph(f"{adresse}\n{telephone} | {email} | Âge : {age}")
        doc.add_heading("Profil", level=1)
        doc.add_paragraph(cv.get("profil", ""))
        doc.add_heading("Compétences", level=1)
        for c in cv.get("competences", []):
            doc.add_paragraph(c, style='List Bullet')
        doc.add_heading("Expériences professionnelles", level=1)
        for e in cv.get("experiences", []):
            doc.add_paragraph(e, style='List Bullet')
        doc.add_heading("Formations", level=1)
        for f in cv.get("formations", []):
            doc.add_paragraph(f, style='List Bullet')
        if cv.get("autres"):
            doc.add_heading("Autres", level=1)
            for a in cv.get("autres", []):
                doc.add_paragraph(a, style='List Bullet')
        doc.save(cv_filepath_docx)

        # LM
        lm_html = render_template("lm_template.html", lettre_motivation=lettre_motivation, nom=nom, prenom=prenom, adresse=adresse, telephone=telephone, email=email, age=age, date_du_jour=date_du_jour)
        lm_filename_pdf = f"{uuid.uuid4().hex}.pdf"
        lm_filepath_pdf = os.path.join(UPLOAD_FOLDER, lm_filename_pdf)
        pdfkit.from_string(lm_html, lm_filepath_pdf)
        lm_filename_docx = f"{uuid.uuid4().hex}.docx"
        lm_filepath_docx = os.path.join(UPLOAD_FOLDER, lm_filename_docx)
        doc_lm = Document()
        doc_lm.add_heading("Lettre de motivation", 0)
        doc_lm.add_paragraph(f"{prenom} {nom}\n{adresse}\n{telephone} | {email} | Âge : {age}\n{date_du_jour}")
        for line in lettre_motivation.split('\n'):
            doc_lm.add_paragraph(line)
        doc_lm.save(lm_filepath_docx)

        # FICHE POSTE
        fiche_html = render_template("fiche_poste_template.html", fiche=fiche_poste)
        fiche_filename_pdf = f"{uuid.uuid4().hex}.pdf"
        fiche_filepath_pdf = os.path.join(UPLOAD_FOLDER, fiche_filename_pdf)
        pdfkit.from_string(fiche_html, fiche_filepath_pdf)
        fiche_filename_docx = f"{uuid.uuid4().hex}.docx"
        fiche_filepath_docx = os.path.join(UPLOAD_FOLDER, fiche_filename_docx)
        doc_fiche = Document()
        doc_fiche.add_heading(fiche_poste.get("titre", ""), 0)
        doc_fiche.add_paragraph(fiche_poste.get("employeur", ""))
        doc_fiche.add_paragraph(fiche_poste.get("ville", ""))
        doc_fiche.add_paragraph(fiche_poste.get("salaire", ""))
        doc_fiche.add_paragraph(fiche_poste.get("type_contrat", ""))
        doc_fiche.add_heading("Missions", level=1)
        for m in fiche_poste.get("missions", []):
            doc_fiche.add_paragraph(m, style='List Bullet')
        doc_fiche.add_heading("Compétences", level=1)
        for c in fiche_poste.get("competences", []):
            doc_fiche.add_paragraph(c, style='List Bullet')
        doc_fiche.add_heading("Avantages", level=1)
        for a in fiche_poste.get("avantages", []):
            doc_fiche.add_paragraph(a, style='List Bullet')
        doc_fiche.add_heading("Savoir-être", level=1)
        for s in fiche_poste.get("savoir_etre", []):
            doc_fiche.add_paragraph(s, style='List Bullet')
        doc_fiche.add_heading("Autres", level=1)
        for o in fiche_poste.get("autres", []):
            doc_fiche.add_paragraph(o, style='List Bullet')
        doc_fiche.save(fiche_filepath_docx)

        # On passe toutes les infos au template résultat
        context.update({
            "nom": nom, "prenom": prenom, "adresse": adresse, "telephone": telephone, "email": email, "age": age,
            "experiences": experiences, "diplomes": diplomes, "offre": offre,
            "cv_uploaded_text": cv_uploaded_text,
            "cv": cv,
            "lettre_motivation": lettre_motivation,
            "fiche_poste": fiche_poste,
            "fiche_file": fiche_filename_pdf,
            "fiche_file_docx": fiche_filename_docx,
            "cv_file": cv_filename_pdf,
            "cv_file_docx": cv_filename_docx,
            "lm_file": lm_filename_pdf,
            "lm_file_docx": lm_filename_docx,
            "date_du_jour": date_du_jour
        })
        return render_template("result.html", **context)

    # --- GET : Affiche la page principale ---
    return render_template("index.html", **context)

@app.route("/download/<path:filename>")
def download_file(filename):
    safe_path = os.path.join(UPLOAD_FOLDER, os.path.basename(filename))
    if not os.path.exists(safe_path):
        return "Fichier introuvable", 404
    return send_file(safe_path, as_attachment=True)

# --- Nettoyage fichiers temporaires à ajouter en tâche CRON ou au démarrage si besoin ---

if __name__ == "__main__":
    import sys
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
