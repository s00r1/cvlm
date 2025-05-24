from flask import Flask, render_template, request, send_file
import pdfkit
import os
import platform
import shutil
from docx import Document
import re
import requests
import time

app = Flask(__name__)

# ================== France Travail / API ROME 4.0 ==================

CLIENT_ID = "PAR_cvlmgenerator_e734f2e5d30360ebf9c08c788cb370deb12aedea1ffd23dc1536f73a16819aac"
CLIENT_SECRET = "e8e427e69c1f76412ff16e816679dfd5507d4ba310102d02f4764c047133c1d8"
TOKEN_URL = "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire"
ROME_API_URL = "https://api.francetravail.io/partenaire/rome-fiches-metiers"

class RomeAPIClient:
    def __init__(self):
        self.token = None
        self.token_expiry = 0

    def get_token(self):
        if self.token and time.time() < self.token_expiry - 300:
            return self.token
        data = {
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "api_rome-fiches-metiersv1"
        }
        r = requests.post(TOKEN_URL, data=data)
        print("AUTH STATUS:", r.status_code)
        print("AUTH RESPONSE:", r.text)
        if r.status_code != 200:
            raise Exception(f"Erreur auth API ROME : {r.status_code} {r.text}")
        resp = r.json()
        self.token = resp['access_token']
        self.token_expiry = time.time() + int(resp['expires_in'])
        return self.token

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.get_token()}"
        }

    def list_metiers(self):
        headers = self.get_headers()
        r = requests.get(ROME_API_URL, headers=headers)
        print("ROME METIERS STATUS:", r.status_code)
        print("ROME METIERS RESPONSE:", r.text)
        if r.status_code == 200:
            return r.json()
        return []

    def get_fiche_metier(self, code):
        url = f"{ROME_API_URL}/{code}"
        headers = self.get_headers()
        r = requests.get(url, headers=headers)
        print(f"ROME FICHE {code} STATUS:", r.status_code)
        print(f"ROME FICHE {code} RESPONSE:", r.text)
        if r.status_code == 200:
            return r.json()
        return None

rome_api_client = RomeAPIClient()

# ================== Extraction texte et parsing ==================

def extract_sections(text):
    lines = text.split('\n')
    sections = {}
    current_section = "Header"
    sections[current_section] = []
    for line in lines:
        l = line.strip()
        if not l:
            continue
        if re.match(r'^[A-ZÉÈÀÂÊÎÔÛÇËÏÜ\- ]{4,}$', l) and len(l.split()) <= 6:
            current_section = l.title()
            sections[current_section] = []
        else:
            sections[current_section].append(l)
    for k in list(sections.keys()):
        sections[k] = [l for l in sections[k] if l and not re.match(r'^[A-ZÉÈÀÂÊÎÔÛÇËÏÜ\- ]{4,}$', l)]
        if not sections[k]:
            del sections[k]
    return sections

def parse_offer(text):
    sections = extract_sections(text)
    header = sections.get('Header', [])
    titre = header[0] if header else ""
    ville = header[1] if len(header) > 1 else ""
    # On tente de récupérer un code métier à partir du titre
    code_rome = ""
    libelle_rome = ""
    missions = []
    competences = []
    savoir_etre = []
    try:
        # On liste tous les métiers ROME
        metiers = rome_api_client.list_metiers()
        # On cherche un métier qui matche le titre (très basique, à améliorer !)
        for m in metiers:
            if titre.lower() in m.get('intitule', '').lower():
                code_rome = m.get('code')
                libelle_rome = m.get('intitule')
                break
        # Si trouvé, on va chercher la fiche complète
        if code_rome:
            fiche_rome = rome_api_client.get_fiche_metier(code_rome)
            # On parse les missions/compétences/savoirs de la fiche API ROME
            if fiche_rome:
                missions = [grp.get('libelle') for grp in fiche_rome.get('groupesCompetences', [])]
                competences = [s.get('libelle') for g in fiche_rome.get('groupesCompetences', []) for s in g.get('competences',[])]
                savoir_etre = [s.get('libelle') for g in fiche_rome.get('groupesSavoirs', []) for s in g.get('savoirs',[])]
    except Exception as e:
        print("Erreur ROME API : ", e)

    # On complète avec le parsing local si besoin
    missions += sections.get("Mission Principale", []) + sections.get("Activités", [])
    competences += sections.get("Compétences Professionnelles", []) + sections.get("Compétences", [])
    savoir_etre += sections.get("Savoir-Être Professionnels", []) + sections.get("Savoir-Être", [])
    profil = sections.get("Profil Souhaité", []) + sections.get("Profil", [])
    avantages = []
    experience = ""
    secteur = ""
    employeur = ""
    salaire = ""
    duree = ""
    contrat = ""
    langues = []
    permis = []
    for k, v in sections.items():
        for l in v:
            if any(x in l.lower() for x in ["véhicule", "chèque", "mutuelle", "repas", "déplacements", "prime", "restauration"]):
                avantages.append(l)
            if "expérien" in l.lower():
                experience = l
            if "secteur d'activité" in l.lower():
                secteur = l.split(":", 1)[-1].strip() if ":" in l else l
            if "employeur" in l.lower():
                employeur = l.split(":", 1)[-1].strip() if ":" in l else l
            if "salaire" in l.lower():
                salaire = l.split(":", 1)[-1].strip() if ":" in l else l
            if "durée" in l.lower():
                duree = l.split(":", 1)[-1].strip() if ":" in l else l
            if "contrat" in l.lower():
                contrat = l.split(":", 1)[-1].strip() if ":" in l else l
            if "langue" in l.lower():
                langues.append(l)
            if "permis" in l.lower():
                permis.append(l)
    if not missions and "Activités" in sections:
        missions = sections["Activités"]
    if not savoir_etre and "Savoir-Etre Professionnels" in sections:
        savoir_etre = sections["Savoir-Etre Professionnels"]
    if not profil:
        profil = []
    if not avantages:
        for l in text.split('\n'):
            if any(x in l.lower() for x in ["véhicule", "chèque", "mutuelle", "repas", "déplacements", "prime", "restauration"]):
                avantages.append(l.strip())
    return dict(
        titre=titre,
        ville=ville,
        code_rome=code_rome,
        libelle_rome=libelle_rome,
        missions=missions,
        competences=competences,
        savoir_etre=savoir_etre,
        profil=profil,
        avantages=avantages,
        experience=experience,
        secteur=secteur,
        employeur=employeur,
        salaire=salaire,
        duree=duree,
        contrat=contrat,
        langues=langues,
        permis=permis
    )

# ================== Génération fichiers ==================

def generate_docx_fiche(fiche):
    doc = Document()
    doc.add_heading(fiche['titre'], 0)
    if fiche['code_rome']:
        doc.add_paragraph(f"Code ROME : {fiche['code_rome']} — {fiche.get('libelle_rome', '')}")
    doc.add_paragraph(fiche['ville'])
    if fiche['employeur']:
        doc.add_paragraph(f"Employeur : {fiche['employeur']}")
    if fiche['contrat']:
        doc.add_paragraph(f"Contrat : {fiche['contrat']}")
    if fiche['duree']:
        doc.add_paragraph(f"Durée : {fiche['duree']}")
    if fiche['salaire']:
        doc.add_paragraph(f"Salaire : {fiche['salaire']}")
    if fiche['avantages']:
        doc.add_heading("Avantages", level=1)
        for av in fiche['avantages']:
            doc.add_paragraph(av, style='List Bullet')
    if fiche['missions']:
        doc.add_heading("Missions / Activités", level=1)
        for m in fiche['missions']:
            doc.add_paragraph(m, style='List Bullet')
    if fiche['competences']:
        doc.add_heading("Compétences", level=1)
        for c in fiche['competences']:
            doc.add_paragraph(c, style='List Bullet')
    if fiche['savoir_etre']:
        doc.add_heading("Savoir-être professionnels", level=1)
        for s in fiche['savoir_etre']:
            doc.add_paragraph(s, style='List Bullet')
    if fiche['experience']:
        doc.add_paragraph(f"Expérience : {fiche['experience']}")
    if fiche['langues']:
        doc.add_paragraph("Langues : " + ', '.join(fiche['langues']))
    if fiche['permis']:
        doc.add_paragraph("Permis : " + ', '.join(fiche['permis']))
    if fiche['secteur']:
        doc.add_paragraph(f"Secteur : {fiche['secteur']}")
    return doc

def generer_cv_text(nom, prenom, age, fiche):
    txt = f"Je m'appelle {prenom} {nom}, j'ai {age} ans. Je souhaite rejoindre votre équipe en tant que {fiche['titre']}."
    if fiche['missions']:
        txt += "\nMissions principales : " + '; '.join(fiche['missions'])
    if fiche['competences']:
        txt += "\nCompétences : " + '; '.join(fiche['competences'])
    if fiche['savoir_etre']:
        txt += "\nSavoir-être : " + ', '.join(fiche['savoir_etre'])
    return txt

def generer_lm_text(nom, prenom, fiche):
    titre = fiche['titre']
    missions = fiche['missions']
    competences = fiche['competences']
    savoir_etre = fiche['savoir_etre']
    txt = (
        f"Madame, Monsieur,\n\n"
        f"Je vous propose ma candidature pour le poste de « {titre} ».\n"
    )
    if missions:
        txt += "Les missions proposées correspondent à mes compétences, notamment :\n"
        for m in missions[:3]:
            txt += f"• {m}\n"
    if competences:
        txt += "Compétences clés : " + ', '.join(competences[:5]) + ".\n"
    if savoir_etre:
        txt += "Savoir-être : " + ', '.join(savoir_etre[:5]) + ".\n"
    txt += (
        "Motivé(e) et sérieux(se), je suis disponible pour un entretien à votre convenance.\n\n"
        f"Cordialement,\n{prenom} {nom}"
    )
    return txt

def generate_docx_cv(nom, prenom, age, adresse, telephone, email, fiche, cv_profile):
    doc = Document()
    doc.add_heading(f"{prenom} {nom}", 0)
    if fiche['code_rome']:
        doc.add_paragraph(f"Code ROME : {fiche['code_rome']} — {fiche.get('libelle_rome', '')}")
    doc.add_paragraph(f"{adresse}\n{telephone} | {email} | {age} ans")
    doc.add_heading("Profil", level=1)
    doc.add_paragraph(cv_profile)
    if fiche['missions']:
        doc.add_heading("Missions", level=1)
        for m in fiche['missions']:
            doc.add_paragraph(m, style='List Bullet')
    if fiche['competences']:
        doc.add_heading("Compétences", level=1)
        for c in fiche['competences']:
            doc.add_paragraph(c, style='List Bullet')
    if fiche['savoir_etre']:
        doc.add_heading("Savoir-être / Qualités", level=1)
        for q in fiche['savoir_etre']:
            doc.add_paragraph(q, style='List Bullet')
    doc.add_heading("Expérience", level=1)
    doc.add_paragraph("Exemple : Employé polyvalent (2022-2023), Entreprise Exemple")
    doc.add_heading("Formation", level=1)
    doc.add_paragraph("Baccalauréat ou équivalent")
    return doc

def generate_docx_lm(nom, prenom, adresse, telephone, email, age, lm_text):
    doc = Document()
    doc.add_heading("Lettre de motivation", 0)
    doc.add_paragraph(f"{prenom} {nom}\n{adresse}\n{telephone} | {email} | {age} ans\n")
    for line in lm_text.split('\n'):
        doc.add_paragraph(line)
    return doc

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

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nom = request.form['nom']
        prenom = request.form['prenom']
        adresse = request.form['adresse']
        telephone = request.form['telephone']
        email = request.form['email']
        age = request.form['age']
        offre = request.form['description'].strip()
        fiche = parse_offer(offre)

        # Génération fiche de poste
        fiche_html = render_template('fiche_poste_template.html', **fiche)
        fiche_pdf = pdfkit.from_string(fiche_html, False, configuration=config)
        fiche_docx = generate_docx_fiche(fiche)
        tmp_fiche_pdf = "tmp_fiche.pdf"
        tmp_fiche_docx = "tmp_fiche.docx"
        with open(tmp_fiche_pdf, "wb") as f:
            f.write(fiche_pdf)
        fiche_docx.save(tmp_fiche_docx)

        # Génération CV & LM
        cv_profile = generer_cv_text(nom, prenom, age, fiche)
        lm_text = generer_lm_text(nom, prenom, fiche)

        cv_html = render_template(
            "cv_template.html",
            nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
            email=email, age=age, offre=offre, cv_profile=cv_profile,
            missions=fiche['missions'], competences=fiche['competences'], savoir_etre=fiche['savoir_etre'],
            code_rome=fiche['code_rome'], libelle_rome=fiche['libelle_rome']
        )
        cv_pdf = pdfkit.from_string(cv_html, False, configuration=config)
        cv_docx = generate_docx_cv(nom, prenom, age, adresse, telephone, email, fiche, cv_profile)

        lm_html = render_template(
            "lm_template.html",
            nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
            email=email, age=age, offre=offre, lm_text=lm_text,
            code_rome=fiche['code_rome'], libelle_rome=fiche['libelle_rome']
        )
        lm_pdf = pdfkit.from_string(lm_html, False, configuration=config)
        lm_docx = generate_docx_lm(nom, prenom, adresse, telephone, email, age, lm_text)

        tmp_cv = "tmp_cv.pdf"
        tmp_cv_docx = "tmp_cv.docx"
        tmp_lm = "tmp_lm.pdf"
        tmp_lm_docx = "tmp_lm.docx"
        with open(tmp_cv, "wb") as f:
            f.write(cv_pdf)
        cv_docx.save(tmp_cv_docx)
        with open(tmp_lm, "wb") as f:
            f.write(lm_pdf)
        lm_docx.save(tmp_lm_docx)

        return render_template(
            "result.html",
            fiche_file=tmp_fiche_pdf, fiche_file_docx=tmp_fiche_docx,
            cv_file=tmp_cv, cv_file_docx=tmp_cv_docx,
            lm_file=tmp_lm, lm_file_docx=tmp_lm_docx
        )
    return render_template("index.html")

@app.route('/download/<filename>')
def download_file(filename):
    if not os.path.exists(filename):
        return "Fichier introuvable", 404
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
