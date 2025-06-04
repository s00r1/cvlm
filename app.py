from flask import Flask, render_template, request, send_file, after_this_request
from jinja2 import Template
import pdfkit
import os
import platform
import shutil
import tempfile
import json
import uuid
from datetime import datetime

from utils_extract import extract_text_from_pdf, extract_text_from_docx
from ai_groq import ask_groq, extract_first_json
from doc_gen import render_cv_docx, render_lm_docx, render_fiche_docx

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

TMP_DIR = "tmp"
os.makedirs(TMP_DIR, exist_ok=True)

def find_wkhtmltopdf():
    path = shutil.which("wkhtmltopdf")
    return path

if platform.system() == "Windows":
    WKHTMLTOPDF_PATH = r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
else:
    wkhtmltopdf_path = find_wkhtmltopdf()
    if wkhtmltopdf_path:
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    else:
        raise RuntimeError("wkhtmltopdf non trouvé sur le système Railway ! Vérifie l'installation.")

app = Flask(__name__)

# ===== PATCH LM mise en page IA =====
def check_lm_paragraphs(lettre):
    return lettre and lettre.count('\n\n') >= 1

def reformat_lm_paragraphs(lettre):
    prompt_format = f"""
Voici une lettre de motivation sans structure paragraphe :

---
{lettre}
---

Reformate exactement ce texte en mettant des doubles sauts de ligne (\\n\\n) entre chaque paragraphe.
N’ajoute, n’enlève ni ne modifie aucune phrase, ne corrige rien, garde tout identique, structure juste les paragraphes.
Donne UNIQUEMENT la lettre reformattée, sans phrase ou indication autour.
"""
    return ask_groq(prompt_format)
# ====================================

# ==== EXTRACTION OFFRE D'EMPLOI PAR URL ====
def extract_text_from_url(url):
    parsed = urlparse(url)
    if not (parsed.scheme in ['http', 'https'] and parsed.netloc):
        return "[Erreur : L’URL fournie n’est pas valide.]"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; OfferScraper/1.0; +https://tonsite.com)"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        cleaned_text = '\n'.join(lines)
        if len(cleaned_text) < 200:
            return "[Erreur : Impossible d’extraire correctement l’offre d’emploi (texte trop court). Essayez de la copier/coller manuellement.]"
        if len(cleaned_text) > 20000:
            return "[Erreur : Texte extrait trop volumineux ou bruité. Veuillez copier/coller manuellement l’offre.]"
        return cleaned_text
    except Exception as e:
        return f"[Erreur lors de la récupération de la page : {e}]"

# ==== VALIDATION IA OFFRE ====
def is_valid_offer_text(offer_text):
    # Appel à Groq pour checker que le texte ressemble à une offre d'emploi
    prompt = f"""
Ce texte est-il une offre d'emploi (annonce complète, française, pour un poste à pourvoir, contenant au moins : titre du poste, missions, profil, type de contrat ou employeur) ?
Réponds uniquement par "OUI" ou "NON" en majuscules.
Texte à analyser :
\"\"\"
{offer_text}
\"\"\"
"""
    resp = ask_groq(prompt)
    return resp.strip().startswith("OUI")

@app.route('/', methods=['GET', 'POST'])
def index():
    error = ""
    context = {
        "nom": "", "prenom": "", "adresse": "", "telephone": "", "email": "", "age": "",
        "xp_poste": [], "xp_entreprise": [], "xp_lieu": [], "xp_debut": [], "xp_fin": [],
        "dip_titre": [], "dip_lieu": [], "dip_date": [],
        "description": ""
    }

    offer_url = ""
    offer_text = ""
    error_offer = ""

    if request.method == 'POST':
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

        offer_url = request.form.get('offer_url', '').strip()
        offer_text = request.form.get('offer_text', '').strip()

        context.update({
            "nom": nom, "prenom": prenom, "adresse": adresse, "telephone": telephone, "email": email, "age": age,
            "xp_poste": xp_poste, "xp_entreprise": xp_entreprise, "xp_lieu": xp_lieu, "xp_debut": xp_debut, "xp_fin": xp_fin,
            "dip_titre": dip_titre, "dip_lieu": dip_lieu, "dip_date": dip_date,
            "description": description
        })

        # ----- LOGIQUE PATCH OFFRE D'EMPLOI : URL / Copie -----
        # 1. Extraction par URL si présente
        if offer_url:
            offer_extracted = extract_text_from_url(offer_url)
            if offer_extracted.startswith("[Erreur"):
                error_offer = offer_extracted
                offer_text = ""  # Laisse vide pour la saisie manuelle
            else:
                offer_text = offer_extracted

        # 2. Validation IA du texte extrait/saisi
        if offer_text and not offer_text.startswith("[Erreur"):
            if not is_valid_offer_text(offer_text):
                error_offer = "Le texte récupéré ne correspond pas à une offre d'emploi complète. Merci de vérifier le texte ou de le saisir manuellement."
                offer_text = ""
        elif not offer_text:
            error_offer = "Merci de saisir ou d'extraire une offre d'emploi valide."

        if error_offer:
            return render_template("index.html", error=error, error_offer=error_offer, offer_url=offer_url, offer_text=offer_text, **context)

        # --- (La suite reste inchangée, description = offer_text) ---
        description = offer_text  # Patch la variable pour pipeline IA

        cv_uploaded_text = ""
        infos_perso = {}
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

        fiche_poste = {}
        file_id = uuid.uuid4().hex

        # -------------- IA ROUTINE -----------------
        if cv_uploaded_text.strip():
            prompt_parse_cv = f"""
Lis attentivement le texte suivant extrait d’un CV PDF ou DOCX. Trie les informations dans ce JSON, section par section, sans jamais inventer :

{{
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

            # Patch Perso fallback
            nom = cv_data.get("nom", nom)
            prenom = cv_data.get("prenom", prenom)
            adresse = cv_data.get("adresse", adresse)
            telephone = cv_data.get("telephone", telephone)
            email = cv_data.get("email", email)
            age = cv_data.get("age", age)
            infos_perso = {
                "nom": nom, "prenom": prenom, "adresse": adresse,
                "telephone": telephone, "email": email, "age": age
            }

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

            # PATCH LM : vérifie et corrige la mise en page (APRES le check JSON !)
            if lettre_motivation and not check_lm_paragraphs(lettre_motivation):
                lettre_motivation = reformat_lm_paragraphs(lettre_motivation)

            # PATCH ULTRA CLEAN : vire tous les artefacts '\n\n', '\\n\\n', '\\n'
            lettre_motivation = lettre_motivation.replace('\\n\\n', '\n').replace('\\n', '\n').replace('\n\n', '\n')

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

            # Variables utiles pour la lettre
            poste = fiche_poste.get("titre", "")
            ville = fiche_poste.get("ville", "") or "Ville"
            date_du_jour = datetime.now().strftime("%d %B %Y")
            destinataire_nom = fiche_poste.get("employeur", "")
            destinataire_etab = fiche_poste.get("employeur", "")
            destinataire_adresse = fiche_poste.get("adresse", "")
            destinataire_cp_ville = fiche_poste.get("ville", "")

            # ---------- Génération fichiers ----------
            cv_pdf_path = os.path.join(TMP_DIR, f"{file_id}_cv.pdf")
            cv_docx_path = os.path.join(TMP_DIR, f"{file_id}_cv.docx")
            lm_pdf_path = os.path.join(TMP_DIR, f"{file_id}_lm.pdf")
            lm_docx_path = os.path.join(TMP_DIR, f"{file_id}_lm.docx")
            fiche_pdf_path = os.path.join(TMP_DIR, f"{file_id}_fiche.pdf")
            fiche_docx_path = os.path.join(TMP_DIR, f"{file_id}_fiche.docx")
            # --- HTML rendering
            with open("templates/cv_template.html", encoding="utf-8") as f:
                cv_html = Template(f.read()).render(cv=cv_adapte, infos_perso=infos_perso, **infos_perso)
            with open("templates/lm_template.html", encoding="utf-8") as f:
                lm_html = Template(f.read()).render(
                    lettre_motivation=lettre_motivation,
                    infos_perso=infos_perso,
                    poste=poste,
                    ville=ville,
                    date_du_jour=date_du_jour,
                    destinataire_nom=destinataire_nom,
                    destinataire_etab=destinataire_etab,
                    destinataire_adresse=destinataire_adresse,
                    destinataire_cp_ville=destinataire_cp_ville
                )
            with open("templates/fiche_poste_template.html", encoding="utf-8") as f:
                fiche_html = Template(f.read()).render(fiche_poste=fiche_poste)
            # --- PDF
            pdfkit.from_string(cv_html, cv_pdf_path, configuration=config)
            pdfkit.from_string(lm_html, lm_pdf_path, configuration=config)
            pdfkit.from_string(fiche_html, fiche_pdf_path, configuration=config)
            # --- DOCX
            render_cv_docx(cv_adapte, infos_perso, cv_docx_path)
            render_lm_docx(lettre_motivation, infos_perso, lm_docx_path)
            render_fiche_docx(fiche_poste, fiche_docx_path)

            return render_template(
                "result.html",
                fiche_poste=fiche_poste,
                cv=cv_adapte,
                lettre_motivation=lettre_motivation,
                infos_perso=infos_perso,
                poste=poste,
                ville=ville,
                date_du_jour=date_du_jour,
                destinataire_nom=destinataire_nom,
                destinataire_etab=destinataire_etab,
                destinataire_adresse=destinataire_adresse,
                destinataire_cp_ville=destinataire_cp_ville,
                cv_uploaded_text=cv_uploaded_text,
                cv_pdf=f"{file_id}_cv.pdf",
                cv_docx=f"{file_id}_cv.docx",
                lm_pdf=f"{file_id}_lm.pdf",
                lm_docx=f"{file_id}_lm.docx",
                fiche_pdf=f"{file_id}_fiche.pdf",
                fiche_docx=f"{file_id}_fiche.docx"
            )

        # ------- Pas de CV uploadé, fallback formulaire -------
        if not ((any(x.strip() for x in xp_poste) and any(x.strip() for x in dip_titre)) or description.strip()):
            error = "Veuillez remplir au moins une expérience professionnelle, un diplôme, ou uploader votre CV."
            return render_template("index.html", error=error, **context)

        prompt_fields = f"""
Voici les infos saisies par le candidat :

Nom : {nom}
Prénom : {prenom}
Adresse : {adresse}
Téléphone : {telephone}
Email : {email}
Âge : {age}

Expériences professionnelles :
{json.dumps(xp_poste)}
Entreprises : {json.dumps(xp_entreprise)}
Lieux : {json.dumps(xp_lieu)}
Dates début : {json.dumps(xp_debut)}
Dates fin : {json.dumps(xp_fin)}

Diplômes : {json.dumps(dip_titre)}
Lieux : {json.dumps(dip_lieu)}
Dates : {json.dumps(dip_date)}

Voici l'offre d'emploi :
\"\"\"
{description}
\"\"\"

Génère une lettre de motivation adaptée à l’offre et au parcours, puis un CV adapté en JSON :

{{
  "lettre_motivation": "...",
  "cv_adapte": {{
    "profil": "...",
    "competences": ["...", "..."],
    "experiences": ["...", "..."],
    "formations": ["...", "..."],
    "autres": ["...", "..."]
  }}
}}
"""
        result2 = ask_groq(prompt_fields)
        data2 = extract_first_json(result2)
        if not data2:
            error = "Erreur IA ou parsing JSON : JSON IA non extrait ou malformé."
            return render_template("index.html", error=error, **context)

        lettre_motivation = data2.get("lettre_motivation", "")
        cv_adapte = data2.get("cv_adapte", {})

        # PATCH LM : vérifie et corrige la mise en page (APRES le check JSON !)
        if lettre_motivation and not check_lm_paragraphs(lettre_motivation):
            lettre_motivation = reformat_lm_paragraphs(lettre_motivation)

        # PATCH ULTRA CLEAN : vire tous les artefacts '\n\n', '\\n\\n', '\\n'
        lettre_motivation = lettre_motivation.replace('\\n\\n', '\n').replace('\\n', '\n').replace('\n\n', '\n')

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

        poste = fiche_poste.get("titre", "")
        ville = fiche_poste.get("ville", "") or "Ville"
        date_du_jour = datetime.now().strftime("%d %B %Y")
        destinataire_nom = fiche_poste.get("employeur", "")
        destinataire_etab = fiche_poste.get("employeur", "")
        destinataire_adresse = fiche_poste.get("adresse", "")
        destinataire_cp_ville = fiche_poste.get("ville", "")

        file_id = uuid.uuid4().hex
        infos_perso = {
            "nom": nom, "prenom": prenom, "adresse": adresse,
            "telephone": telephone, "email": email, "age": age
        }
        # --- HTML rendering
        with open("templates/cv_template.html", encoding="utf-8") as f:
            cv_html = Template(f.read()).render(cv=cv_adapte, infos_perso=infos_perso, **infos_perso)
        with open("templates/lm_template.html", encoding="utf-8") as f:
            lm_html = Template(f.read()).render(
                lettre_motivation=lettre_motivation,
                infos_perso=infos_perso,
                poste=poste,
                ville=ville,
                date_du_jour=date_du_jour,
                destinataire_nom=destinataire_nom,
                destinataire_etab=destinataire_etab,
                destinataire_adresse=destinataire_adresse,
                destinataire_cp_ville=destinataire_cp_ville
            )
        with open("templates/fiche_poste_template.html", encoding="utf-8") as f:
            fiche_html = Template(f.read()).render(fiche_poste=fiche_poste)
        # --- PDF
        cv_pdf_path = os.path.join(TMP_DIR, f"{file_id}_cv.pdf")
        lm_pdf_path = os.path.join(TMP_DIR, f"{file_id}_lm.pdf")
        fiche_pdf_path = os.path.join(TMP_DIR, f"{file_id}_fiche.pdf")
        pdfkit.from_string(cv_html, cv_pdf_path, configuration=config)
        pdfkit.from_string(lm_html, lm_pdf_path, configuration=config)
        pdfkit.from_string(fiche_html, fiche_pdf_path, configuration=config)
        # --- DOCX
        cv_docx_path = os.path.join(TMP_DIR, f"{file_id}_cv.docx")
        lm_docx_path = os.path.join(TMP_DIR, f"{file_id}_lm.docx")
        fiche_docx_path = os.path.join(TMP_DIR, f"{file_id}_fiche.docx")
        render_cv_docx(cv_adapte, infos_perso, cv_docx_path)
        render_lm_docx(lettre_motivation, infos_perso, lm_docx_path)
        render_fiche_docx(fiche_poste, fiche_docx_path)

        return render_template(
            "result.html",
            fiche_poste=fiche_poste,
            cv=cv_adapte,
            lettre_motivation=lettre_motivation,
            infos_perso=infos_perso,
            poste=poste,
            ville=ville,
            date_du_jour=date_du_jour,
            destinataire_nom=destinataire_nom,
            destinataire_etab=destinataire_etab,
            destinataire_adresse=destinataire_adresse,
            destinataire_cp_ville=destinataire_cp_ville,
            cv_uploaded_text="",
            cv_pdf=f"{file_id}_cv.pdf",
            cv_docx=f"{file_id}_cv.docx",
            lm_pdf=f"{file_id}_lm.pdf",
            lm_docx=f"{file_id}_lm.docx",
            fiche_pdf=f"{file_id}_fiche.pdf",
            fiche_docx=f"{file_id}_fiche.docx"
        )

    return render_template("index.html", error=error, error_offer=error_offer, offer_url=offer_url, offer_text=offer_text, **context)

@app.route('/download/<path:filename>')
def download_file(filename):
    full_path = os.path.join(TMP_DIR, os.path.basename(filename))
    if not os.path.exists(full_path):
        return "Fichier introuvable", 404

    @after_this_request
    def remove_file(response):
        try:
            os.remove(full_path)
        except Exception as e:
            app.logger.error(f"Erreur suppression fichier temporaire: {e}")
        return response

    return send_file(full_path, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
