from flask import Flask, render_template, request, send_file
from jinja2 import Template
import pdfkit
import os
import platform
import shutil
from docx import Document

app = Flask(__name__)

def parse_fiche_poste(offre):
    lignes = [l.strip() for l in offre.split('\n') if l.strip()]
    titre = lignes[1] if len(lignes) > 1 else ""
    localisation = ""
    employeur = ""
    contact = ""
    contrat = ""
    salaire = ""
    duree = ""
    non_loge = ""
    missions = []
    attitudes = []
    qualites = []
    experience = ""
    langues = ""
    secteur = ""
    employeur_detail = ""
    current_section = None

    for idx, l in enumerate(lignes):
        l_low = l.lower()
        if not localisation and "localiser avec mappy" in l_low:
            localisation = l.split('-')[1].strip() if '-' in l else l.strip()
        if "employeur" in l_low or "hotel" in l_low or "entreprise" in l_low:
            employeur = l.strip()
        if "contact" in l_low and '@' in l:
            contact = l.strip().replace("Contact :", "").strip()
        if "contrat" in l_low or "type de contrat" in l_low:
            contrat = l.replace("Type de contrat", "").replace("Contrat travail", "").strip(": ").strip()
        if "salaire" in l_low:
            salaire = l.replace("Salaire", "").replace("brut", "brut").strip(": ").strip()
        if "durée du travail" in l_low or "durée" in l_low:
            duree = l.replace("Durée du travail", "").replace("Durée", "").strip(": ").strip()
        if "non logé" in l_low:
            non_loge = "Oui"
        if "secteur d'activité" in l_low:
            secteur = l.replace("Secteur d'activité :", "").strip()
        if "expérience" in l_low:
            experience = l.replace("Expérience", "").replace("Expérience :", "").strip()
        if "langues" in l_low:
            langues = l.replace("Langues", "").replace("Langues :", "").strip()
        if "entreprise" in l_low or "employeur" in l_low:
            employeur_detail = l.replace("Entreprise :", "").replace("Employeur :", "").strip()
        if l_low.startswith("missions principales"):
            current_section = "missions"
            continue
        if l_low.startswith("attitudes de service") or l_low.startswith("relation client"):
            current_section = "attitudes"
            continue
        if l_low.startswith("compétences") or l_low.startswith("savoir-être") or l_low.startswith("profil"):
            current_section = "qualites"
            continue
        if l.startswith("-") or l.startswith("•"):
            content = l.lstrip("-• ").capitalize()
            if current_section == "missions":
                missions.append(content)
            elif current_section == "attitudes":
                attitudes.append(content)
            elif current_section == "qualites":
                qualites.append(content)
    if not missions:
        all_puces = [l.lstrip("-• ").capitalize() for l in lignes if l.startswith("-") or l.startswith("•")]
        missions = all_puces[:8]
        if not attitudes and len(all_puces) > 8:
            attitudes = all_puces[8:16]

    return dict(
        titre=titre,
        localisation=localisation,
        employeur=employeur,
        contact=contact,
        contrat=contrat,
        salaire=salaire,
        duree=duree,
        non_loge=non_loge,
        missions=missions,
        attitudes=attitudes,
        qualites=qualites,
        experience=experience,
        langues=langues,
        secteur=secteur,
        employeur_detail=employeur_detail
    )

def generate_docx_fiche(fiche):
    doc = Document()
    doc.add_heading(fiche['titre'], 0)
    doc.add_paragraph(f"{fiche['localisation']}")
    doc.add_paragraph(f"Employeur : {fiche['employeur']}")
    if fiche['contact']:
        doc.add_paragraph(f"Contact : {fiche['contact']}")
    doc.add_paragraph(f"Type de contrat : {fiche['contrat']}")
    if fiche['salaire']:
        doc.add_paragraph(f"Salaire : {fiche['salaire']}")
    if fiche['duree']:
        doc.add_paragraph(f"Durée : {fiche['duree']}")
    if fiche['non_loge']:
        doc.add_paragraph(f"Non logé : Oui")
    if fiche['missions']:
        doc.add_heading("Missions principales", level=1)
        for m in fiche['missions']:
            doc.add_paragraph(m, style='List Bullet')
    if fiche['attitudes']:
        doc.add_heading("Attitudes de service / Relation client", level=1)
        for m in fiche['attitudes']:
            doc.add_paragraph(m, style='List Bullet')
    if fiche['qualites']:
        doc.add_heading("Compétences, Savoir-être et Profil", level=1)
        for q in fiche['qualites']:
            doc.add_paragraph(q, style='List Bullet')
    if fiche['experience']:
        doc.add_paragraph(f"Expérience : {fiche['experience']}")
    if fiche['langues']:
        doc.add_paragraph(f"Langues : {fiche['langues']}")
    if fiche['secteur']:
        doc.add_paragraph(f"Secteur : {fiche['secteur']}")
    if fiche['employeur_detail']:
        doc.add_paragraph(f"Entreprise : {fiche['employeur_detail']}")
    return doc

def generer_cv_text(nom, prenom, age, fiche):
    missions = fiche['missions']
    qualites = fiche['qualites']
    return (
        f"Je m'appelle {prenom} {nom}, j'ai {age} ans. "
        f"Je possède une forte motivation pour ce poste et des compétences adaptées aux missions suivantes : "
        + (", ".join(missions) if missions else "non précisées")
        + ".\nSavoir-être : "
        + (", ".join(qualites) if qualites else "professionnalisme, motivation, rigueur")
    )

def generer_lm_text(nom, prenom, fiche):
    titre = fiche['titre']
    missions = fiche['missions']
    qualites = fiche['qualites']
    return (
        f"Madame, Monsieur,\n\n"
        f"Je vous propose ma candidature pour le poste de « {titre} ».\n"
        f"Votre annonce correspond à mon profil. J’ai relevé que les principales missions sont :\n"
        + ''.join(f"• {m}\n" for m in missions[:3])
        + "\n"
        f"Mes principaux atouts : {', '.join(qualites) if qualites else 'rigueur, autonomie, sens du service'}.\n"
        f"Motivé(e), sérieux(se) et passionné(e), je suis disponible pour un entretien à votre convenance.\n\n"
        f"Cordialement,\n{prenom} {nom}"
    )

def generate_docx_cv(nom, prenom, age, adresse, telephone, email, fiche, cv_profile):
    doc = Document()
    doc.add_heading(f"{prenom} {nom}", 0)
    doc.add_paragraph(f"{adresse}\n{telephone} | {email} | {age} ans")
    doc.add_heading("Profil", level=1)
    doc.add_paragraph(cv_profile)
    doc.add_heading("Missions/Compétences clés", level=1)
    for m in fiche['missions']:
        doc.add_paragraph(m, style='List Bullet')
    doc.add_heading("Savoir-être / Qualités", level=1)
    for q in fiche['qualites']:
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
    WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
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
        fiche = parse_fiche_poste(offre)

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

        with open('cv_template.html', encoding="utf-8") as f:
            cv_html = Template(f.read()).render(
                nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
                email=email, age=age, offre=offre, cv_profile=cv_profile, missions=fiche['missions'], qualites=fiche['qualites']
            )
        cv_pdf = pdfkit.from_string(cv_html, False, configuration=config)
        cv_docx = generate_docx_cv(nom, prenom, age, adresse, telephone, email, fiche, cv_profile)

        with open('lm_template.html', encoding="utf-8") as f:
            lm_html = Template(f.read()).render(
                nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
                email=email, age=age, offre=offre, lm_text=lm_text
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
