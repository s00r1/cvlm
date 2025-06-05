from flask import Flask, render_template, request, send_file, after_this_request
from pathlib import Path
from jinja2 import Template
import pdfkit
import os
import platform
import shutil
import tempfile
import json
import uuid
from datetime import datetime
import time

from utils_extract import extract_text_from_pdf, extract_text_from_docx
from ai_groq import ask_groq, extract_first_json
from doc_gen import render_cv_docx, render_lm_docx, render_fiche_docx
from extract_offer import extract_text_from_url

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
        raise RuntimeError(
            "wkhtmltopdf non trouvé sur le système Railway ! Vérifie l'installation."
        )

app = Flask(__name__)

# Base64-encoded 1x1 white JPEG used as placeholder for the premium template
PREMIUM_PLACEHOLDER_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwg"
    "JC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QA"
    "HwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIh"
    "MUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVW"
    "V1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG"
    "x8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQF"
    "BgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAV"
    "YnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOE"
    "hYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq"

    "8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=="
)

# If True, a photo upload is mandatory when using the premium template.
# When False (default), the tiny white placeholder above will be used if no
# photo is provided.
PREMIUM_PHOTO_REQUIRED = False


def cleanup_tmp_dir(max_age_seconds=3600):
    """Remove files older than ``max_age_seconds`` from TMP_DIR."""
    now = time.time()
    for fname in os.listdir(TMP_DIR):
        path = os.path.join(TMP_DIR, fname)
        try:
            if os.path.isfile(path) and now - os.path.getmtime(path) > max_age_seconds:
                os.remove(path)
        except Exception as e:
            app.logger.error(f"Erreur nettoyage fichiers temporaires: {e}")


cleanup_tmp_dir()


# ===== PATCH LM mise en page IA =====
def check_lm_paragraphs(lettre):
    return lettre and lettre.count("\n\n") >= 1


def reformat_lm_paragraphs(lettre):
    prompt_format = f"""
Voici une lettre de motivation sans structure paragraphe :

---
{lettre}
---

Reformate exactement ce texte en mettant des doubles sauts de ligne (\\n\\n) entre chaque paragraphe.  # noqa: E501
N’ajoute, n’enlève ni ne modifie aucune phrase, ne corrige rien, garde tout identique, structure juste les paragraphes.  # noqa: E501
Donne UNIQUEMENT la lettre reformattée, sans phrase ou indication autour.  # noqa: E501
"""
    return ask_groq(prompt_format)


# ====================================

# ==== EXTRACTION OFFRE D'EMPLOI PAR URL ====


# ==== VALIDATION IA OFFRE ====
def is_valid_offer_text(offer_text):
    # Appel à Groq pour checker que le texte ressemble à une offre d'emploi
    prompt = f"""
Ce texte est-il une offre d'emploi (annonce complète, française, pour un poste à pourvoir, contenant au moins : titre du poste, missions, profil, type de contrat ou employeur) ?  # noqa: E501
Réponds uniquement par "OUI" ou "NON" en majuscules.  # noqa: E501
Texte à analyser :
\"\"\"
{offer_text}
\"\"\"
"""
    resp = ask_groq(prompt)
    return resp.strip().startswith("OUI")


def generate_documents(
    cv_adapte,
    lettre_motivation,
    fiche_poste,
    infos_perso,
    template_choice,
    photo_path,
    file_id,
    cv_uploaded_text="",
    tmp_photo_name=None,
):
    """Create PDF/DOCX files and render the result page."""
    poste = fiche_poste.get("titre", "")
    ville = fiche_poste.get("ville", "") or "Ville"
    date_du_jour = datetime.now().strftime("%d %B %Y")
    destinataire_nom = fiche_poste.get("employeur", "")
    destinataire_etab = fiche_poste.get("employeur", "")
    destinataire_adresse = fiche_poste.get("adresse", "")
    destinataire_cp_ville = fiche_poste.get("ville", "")

    cv_pdf_path = os.path.join(TMP_DIR, f"{file_id}_cv.pdf")
    cv_docx_path = os.path.join(TMP_DIR, f"{file_id}_cv.docx")
    lm_pdf_path = os.path.join(TMP_DIR, f"{file_id}_lm.pdf")
    lm_docx_path = os.path.join(TMP_DIR, f"{file_id}_lm.docx")
    fiche_pdf_path = os.path.join(TMP_DIR, f"{file_id}_fiche.pdf")
    fiche_docx_path = os.path.join(TMP_DIR, f"{file_id}_fiche.docx")

    css_file = (
        "static/cv_theme.css"
        if template_choice != "premium"
        else "static/cv_premium.css"
    )
    css_path = f"file://{Path(css_file).resolve()}"
    tpl_file = (
        "templates/cv_template.html"
        if template_choice != "premium"
        else "templates/cv_template_premium.html"
    )
    with open(tpl_file, encoding="utf-8") as f:
        cv_html = Template(f.read()).render(
            cv=cv_adapte,
            infos_perso=infos_perso,
            css_path=css_path,
            photo_path=photo_path,
            **infos_perso,
        )
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
            destinataire_cp_ville=destinataire_cp_ville,
        )
    with open("templates/fiche_poste_template.html", encoding="utf-8") as f:
        fiche_html = Template(f.read()).render(fiche_poste=fiche_poste)

    pdfkit.from_string(
        cv_html,
        cv_pdf_path,
        configuration=config,
        options={"enable-local-file-access": ""},
    )
    pdfkit.from_string(
        lm_html,
        lm_pdf_path,
        configuration=config,
        options={"enable-local-file-access": ""},
    )
    pdfkit.from_string(
        fiche_html,
        fiche_pdf_path,
        configuration=config,
        options={"enable-local-file-access": ""},
    )

    render_cv_docx(cv_adapte, infos_perso, cv_docx_path)
    render_lm_docx(lettre_motivation, infos_perso, lm_docx_path)
    render_fiche_docx(fiche_poste, fiche_docx_path)

    if tmp_photo_name:
        os.remove(tmp_photo_name)

    current_year = datetime.now().year
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
        fiche_docx=f"{file_id}_fiche.docx",
        current_year=current_year,
    )


@app.route("/", methods=["GET", "POST"])
def index():
    error = ""
    current_year = datetime.now().year
    context = {
        "nom": "",
        "prenom": "",
        "adresse": "",
        "telephone": "",
        "email": "",
        "age": "",
        "xp_poste": [],
        "xp_entreprise": [],
        "xp_lieu": [],
        "xp_debut": [],
        "xp_fin": [],
        "dip_titre": [],
        "dip_lieu": [],
        "dip_date": [],
        "description": "",
        "template": "basic",
    }

    offer_url = ""
    offer_text = ""
    error_offer = ""

    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        adresse = request.form.get("adresse", "").strip()
        telephone = request.form.get("telephone", "").strip()
        email = request.form.get("email", "").strip()
        age = request.form.get("age", "").strip()
        description = request.form.get("description", "").strip()
        xp_poste = request.form.getlist("xp_poste")
        xp_entreprise = request.form.getlist("xp_entreprise")
        xp_lieu = request.form.getlist("xp_lieu")
        xp_debut = request.form.getlist("xp_debut")
        xp_fin = request.form.getlist("xp_fin")
        dip_titre = request.form.getlist("dip_titre")
        dip_lieu = request.form.getlist("dip_lieu")
        dip_date = request.form.getlist("dip_date")
        cv_file = request.files.get("cv_file")
        template_choice = request.form.get("template", "basic")
        photo = request.files.get("photo")

        offer_url = request.form.get("offer_url", "").strip()
        offer_text = request.form.get("offer_text", "").strip()

        context.update(
            {
                "nom": nom,
                "prenom": prenom,
                "adresse": adresse,
                "telephone": telephone,
                "email": email,
                "age": age,
                "xp_poste": xp_poste,
                "xp_entreprise": xp_entreprise,
                "xp_lieu": xp_lieu,
                "xp_debut": xp_debut,
                "xp_fin": xp_fin,
                "dip_titre": dip_titre,
                "dip_lieu": dip_lieu,
                "dip_date": dip_date,
                "description": description,
                "template": template_choice,
            }
        )

        photo_path = ""
        tmp_photo_name = None
        if template_choice == "premium":
            if photo and photo.filename:
                ext = os.path.splitext(photo.filename)[1]
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=ext, dir=TMP_DIR
                ) as tmp_img:
                    photo.save(tmp_img.name)
                    photo_path = f"file://{Path(tmp_img.name).resolve()}"
                    tmp_photo_name = tmp_img.name
            else:
                if PREMIUM_PHOTO_REQUIRED:
                    error = "Veuillez ajouter une photo"
                    return render_template(
                        "index.html",
                        error=error,
                        error_offer=error_offer,
                        offer_url=offer_url,
                        offer_text=offer_text,
                        current_year=current_year,
                        **context,
                    )
                else:
                    photo_path = (
                        f"data:image/jpeg;base64,{PREMIUM_PLACEHOLDER_B64}"
                    )

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
                error_offer = (
                    "Le texte récupéré ne correspond pas à une offre d'emploi "
                    "complète. "
                    "Merci de vérifier le texte ou de le saisir manuellement."
                )
                offer_text = ""
        elif not offer_text:
            error_offer = "Merci de saisir ou d'extraire une offre d'emploi valide."

        if error_offer:
            return render_template(
                "index.html",
                error=error,
                error_offer=error_offer,
                offer_url=offer_url,
                offer_text=offer_text,
                current_year=current_year,
                **context,
            )

        # --- (La suite reste inchangée, description = offer_text) ---
        description = offer_text  # Patch la variable pour pipeline IA

        cv_uploaded_text = ""
        infos_perso = {}
        if cv_file and cv_file.filename:
            ext = cv_file.filename.lower().split(".")[-1]
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
            prompt_parse_cv = (
                "Lis attentivement le texte suivant extrait d’un CV PDF ou DOCX. "
                "Trie les informations dans ce JSON, section par section, sans jamais "
                "inventer :\n"
                "{\n"
                '  "nom": "...",\n'
                '  "prenom": "...",\n'
                '  "adresse": "...",\n'
                '  "telephone": "...",\n'
                '  "email": "...",\n'
                '  "age": "...",\n'
                '  "profil": "...",\n'
                '  "competences": ["...", "..."],\n'
                '  "experiences": ["...", "..."],\n'
                '  "formations": ["...", "..."],\n'
                '  "autres": ["...", "..."]\n'
                "}\n"
                "\n"
                "Si tu ne trouves pas une section, laisse-la vide, mais structure "
                "toujours le JSON comme ci-dessus.\n"
                "\n"
                "TEXTE DU CV À PARSER :\n"
                '"""\n'
                f"{cv_uploaded_text}\n"
                '"""'
            )
            parsed_cv_json = ask_groq(prompt_parse_cv)
            cv_data = extract_first_json(parsed_cv_json)
            if not cv_data:
                error = "Erreur extraction IA du CV : JSON IA non extrait ou malformé."
                return render_template(
                    "index.html",
                    error=error,
                    current_year=current_year,
                    **context,
                )

            # Patch Perso fallback
            nom = cv_data.get("nom", nom)
            prenom = cv_data.get("prenom", prenom)
            adresse = cv_data.get("adresse", adresse)
            telephone = cv_data.get("telephone", telephone)
            email = cv_data.get("email", email)
            age = cv_data.get("age", age)
            infos_perso = {
                "nom": nom,
                "prenom": prenom,
                "adresse": adresse,
                "telephone": telephone,
                "email": email,
                "age": age,
            }

            prompt_lm_cv = (
                "Voici le parsing structuré du CV du candidat, issu de l’étape "
                "précédente :\n"
                f"{json.dumps(cv_data, ensure_ascii=False, indent=2)}\n\n"
                "Voici l'offre d'emploi à laquelle il postule :\n"
                '"""\n'
                f"{description}\n"
                '"""\n\n'
                "1. Rédige une lettre de motivation personnalisée et professionnelle "
                "adaptée à l'offre et au parcours du candidat (exploite le maximum "
                "d’infos utiles, mets en avant les expériences ou compétences "
                "transversales si besoin).\n"
                "2. Génère le contenu d’un CV adapté à l’offre, en sélectionnant :\n"
                "   - Un paragraphe de profil synthétique (adapté au poste)\n"
                "   - Les compétences les plus pertinentes (croisées entre CV et "
                "offre)\n"
                "   - Les expériences professionnelles les plus adaptées, "
                "sous forme de bullet points (intitulé, entreprise, dates, "
                "mission principale)\n"
                "   - Les formations principales\n"
                "   - Autres infos utiles\n\n"
                "Rends ce JSON strictement :\n"
                "{{\n"
                '  "lettre_motivation": "....",\n'
                '  "cv_adapte": {\n'
                '    "profil": "...",\n'
                '    "competences": ["...", "..."],\n'
                '    "experiences": ["...", "..."],\n'
                '    "formations": ["...", "..."],\n'
                '    "autres": ["...", "..."]\n'
                "  }\n"
                "}}"
            )
            result2 = ask_groq(prompt_lm_cv)
            data2 = extract_first_json(result2)
            if not data2:
                error = "Erreur extraction IA LM/CV : JSON IA non extrait ou malformé."
                return render_template(
                    "index.html",
                    error=error,
                    current_year=current_year,
                    **context,
                )

            lettre_motivation = data2.get("lettre_motivation", "")
            cv_adapte = data2.get("cv_adapte", {})

            # PATCH LM : vérifie et corrige la mise en page (APRES le check JSON !)
            if lettre_motivation and not check_lm_paragraphs(lettre_motivation):
                lettre_motivation = reformat_lm_paragraphs(lettre_motivation)

            # PATCH ULTRA CLEAN : vire tous les artefacts '\n\n', '\\n\\n', '\\n'
            lettre_motivation = (
                lettre_motivation.replace("\\n\\n", "\n")
                .replace("\\n", "\n")
                .replace("\n\n", "\n")
            )

        prompt_fiche_poste = (
            "Lis attentivement l'offre d'emploi suivante et extrait-en les éléments "
            "principaux pour générer une fiche de poste structurée, en "
            "remplissant strictement ce JSON (sans inventer) :\n"
            "{\n"
            '  "titre": "...",\n'
            '  "employeur": "...",\n'
            '  "ville": "...",\n'
            '  "salaire": "...",\n'
            '  "type_contrat": "...",\n'
            '  "missions": ["...", "..."],\n'
            '  "competences": ["...", "..."],\n'
            '  "avantages": ["...", "..."],\n'
            '  "savoir_etre": ["...", "..."],\n'
            '  "autres": ["..."]\n'
            "}\n\n"
            "Offre à analyser :\n"
            '"""\n'
            f"{description}\n"
            '"""'
        )
        fiche_poste_json = ask_groq(prompt_fiche_poste)
        fiche_poste = extract_first_json(fiche_poste_json) or {}

        return generate_documents(
            cv_adapte,
            lettre_motivation,
            fiche_poste,
            infos_perso,
            template_choice,
            photo_path,
            file_id,
            cv_uploaded_text=cv_uploaded_text,
            tmp_photo_name=tmp_photo_name,
        )

        # ------- Pas de CV uploadé, fallback formulaire -------
        if not (
            (any(x.strip() for x in xp_poste) and any(x.strip() for x in dip_titre))
            or description.strip()
        ):
            error = (
                "Veuillez remplir au moins une expérience professionnelle, un diplôme, "
                "ou uploader votre CV."
            )
            return render_template(
                "index.html",
                error=error,
                current_year=current_year,
                **context,
            )

        prompt_fields = (
            "Voici les infos saisies par le candidat :\n\n"
            f"Nom : {nom}\n"
            f"Prénom : {prenom}\n"
            f"Adresse : {adresse}\n"
            f"Téléphone : {telephone}\n"
            f"Email : {email}\n"
            f"Âge : {age}\n\n"
            "Expériences professionnelles :\n"
            f"{json.dumps(xp_poste)}\n"
            f"Entreprises : {json.dumps(xp_entreprise)}\n"
            f"Lieux : {json.dumps(xp_lieu)}\n"
            f"Dates début : {json.dumps(xp_debut)}\n"
            f"Dates fin : {json.dumps(xp_fin)}\n\n"
            f"Diplômes : {json.dumps(dip_titre)}\n"
            f"Lieux : {json.dumps(dip_lieu)}\n"
            f"Dates : {json.dumps(dip_date)}\n\n"
            "Voici l'offre d'emploi :\n"
            '"""\n'
            f"{description}\n"
            '"""\n\n'
            "Génère une lettre de motivation adaptée à l’offre et au parcours, "
            "puis un CV adapté en JSON :\n"
            "{{\n"
            '  "lettre_motivation": "...",\n'
            '  "cv_adapte": {\n'
            '    "profil": "...",\n'
            '    "competences": ["...", "..."],\n'
            '    "experiences": ["...", "..."],\n'
            '    "formations": ["...", "..."],\n'
            '    "autres": ["...", "..."]\n'
            "  }\n"
            "}}"
        )
        result2 = ask_groq(prompt_fields)
        data2 = extract_first_json(result2)
        if not data2:
            error = "Erreur IA ou parsing JSON : JSON IA non extrait ou malformé."
            return render_template(
                "index.html",
                error=error,
                current_year=current_year,
                **context,
            )

        lettre_motivation = data2.get("lettre_motivation", "")
        cv_adapte = data2.get("cv_adapte", {})

        # PATCH LM : vérifie et corrige la mise en page (APRES le check JSON !)
        if lettre_motivation and not check_lm_paragraphs(lettre_motivation):
            lettre_motivation = reformat_lm_paragraphs(lettre_motivation)

        # PATCH ULTRA CLEAN : vire tous les artefacts '\n\n', '\\n\\n', '\\n'
        lettre_motivation = (
            lettre_motivation.replace("\\n\\n", "\n")
            .replace("\\n", "\n")
            .replace("\n\n", "\n")
        )

        prompt_fiche_poste = (
            "Lis attentivement l'offre d'emploi suivante et extrait-en les éléments "
            "principaux pour générer une fiche de poste structurée, en "
            "remplissant strictement ce JSON (sans inventer) :\n"
            "{\n"
            '  "titre": "...",\n'
            '  "employeur": "...",\n'
            '  "ville": "...",\n'
            '  "salaire": "...",\n'
            '  "type_contrat": "...",\n'
            '  "missions": ["...", "..."],\n'
            '  "competences": ["...", "..."],\n'
            '  "avantages": ["...", "..."],\n'
            '  "savoir_etre": ["...", "..."],\n'
            '  "autres": ["..."]\n'
            "}\n\n"
            "Offre à analyser :\n"
            '"""\n'
            f"{description}\n"
            '"""'
        )
        fiche_poste_json = ask_groq(prompt_fiche_poste)
        fiche_poste = extract_first_json(fiche_poste_json) or {}

        file_id = uuid.uuid4().hex
        infos_perso = {
            "nom": nom,
            "prenom": prenom,
            "adresse": adresse,
            "telephone": telephone,
            "email": email,
            "age": age,
        }

        return generate_documents(
            cv_adapte,
            lettre_motivation,
            fiche_poste,
            infos_perso,
            template_choice,
            photo_path,
            file_id,
            tmp_photo_name=tmp_photo_name,
        )

    return render_template(
        "index.html",
        error=error,
        error_offer=error_offer,
        offer_url=offer_url,
        offer_text=offer_text,
        current_year=current_year,
        **context,
    )


@app.route("/download/<path:filename>")
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


@app.after_request
def run_cleanup(response):
    cleanup_tmp_dir()
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
