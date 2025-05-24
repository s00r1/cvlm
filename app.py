from flask import Flask, render_template, request, send_file
from jinja2 import Template
import pdfkit
import io
import os
import platform
import re
import shutil
from docx import Document
from docx.shared import Pt

app = Flask(__name__)

def extraire_missions(offre):
    lignes = offre.split('\n')
    missions = []
    for l in lignes:
        l = l.strip()
        if l.startswith("-") or l.startswith("•"):
            missions.append(l.lstrip("-• ").capitalize())
    return missions[:6]  # max 6 missions

def extraire_qualites(offre):
    mots_clefs = [
        "autonomie", "réactivité", "polyvalent", "rigoureux", "accueil", "relationnel",
        "écoute", "organisation", "maîtrise de soi", "commercial", "service", "anticipation"
    ]
    results = []
    for mot in mots_clefs:
        if mot in offre.lower():
            results.append(mot.capitalize())
    return list(set(results))  # uniques

def generer_cv_text(nom, prenom, age, offre, missions, qualites):
    texte = (
        f"Je m'appelle {prenom} {nom}, j'ai {age} ans. "
        f"Je possède une forte motivation pour ce poste et des compétences adaptées aux missions suivantes : "
        + (", ".join(missions) if missions else "non précisées")
        + ".\nSavoir-être : "
        + (", ".join(qualites) if qualites else "professionnalisme, motivation, rigueur")
    )
    return texte

def generer_lm_text(nom, prenom, offre, missions, qualites):
    titre = offre.split('\n')[0][:70]
    texte = (
        f"Madame, Monsieur,\n\n"
        f"Je vous propose ma candidature pour le poste de « {titre} ».\n"
        f"Votre annonce correspond à mon profil. J’ai relevé que les principales missions sont :\n"
    )
    if missions:
        texte += ''.join(f"• {m}\n" for m in missions[:3])
    else:
        texte += "• Missions non précisées\n"
    texte += (
        "\n"
        f"Mes principaux atouts : {', '.join(qualites) if qualites else 'rigueur, autonomie, sens du service'}.\n"
        f"Motivé(e), sérieux(se) et passionné(e), je suis disponible pour un entretien à votre convenance.\n\n"
        f"Cordialement,\n{prenom} {nom}"
    )
    return texte

def generer_fiche_poste_text(offre, missions, qualites):
    lignes = offre.split('\n')
    titre = lignes[0] if lignes else ""
    avantages = []
    for l in lignes:
        if "salaire" in l.lower() or "prime" in l.lower() or "avantage" in l.lower():
            avantages.append(l.strip())
    texte = f"📋 Fiche de poste\n\n"
    texte += f"**Titre du poste :** {titre}\n\n"
    if missions:
        texte += "**Missions principales :**\n" + ''.join(f"- {m}\n" for m in missions)
    if qualites:
        texte += "\n**Qualités recherchées :** " + ', '.join(qualites) + "\n"
    if avantages:
        texte += "\n**Salaire & Avantages :**\n" + ''.join(f"- {a}\n" for a in avantages)
    texte += "\n\n**Résumé de l'offre :**\n" + '\n'.join(lignes[:10])
    return texte

def generate_docx_cv(nom, prenom, age, adresse, telephone, email, missions, qualites, cv_profile):
    doc = Document()
    doc.add_heading(f"{prenom} {nom}", 0)
    doc.add_paragraph(f"{adresse}\n{telephone} | {email} | {age} ans")
    doc.add_heading("Profil", level=1)
    doc.add_paragraph(cv_profile)
    doc.add_heading("Missions/Compétences clés", level=1)
    for m in missions:
        doc.add_paragraph(m, style='List Bullet')
    doc.add_heading("Savoir-être / Qualités", level=1)
    for q in qualites:
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

def generate_docx_fiche(fiche_text):
    doc = Document()
    doc.add_heading("Fiche de poste", 0)
    for line in fiche_text.split('\n'):
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

        missions = extraire_missions(offre)
        qualites = extraire_qualites(offre)
        cv_profile = generer_cv_text(nom, prenom, age, offre, missions, qualites)
        lm_text = generer_lm_text(nom, prenom, offre, missions, qualites)
        fiche_text = generer_fiche_poste_text(offre, missions, qualites)

        # Générer les PDFs (CV & LM)
        with open('cv_template.html', encoding="utf-8") as f:
            cv_html = Template(f.read()).render(
                nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
                email=email, age=age, offre=offre, cv_profile=cv_profile, missions=missions, qualites=qualites
            )
        cv_pdf = pdfkit.from_string(cv_html, False, configuration=config)

        with open('lm_template.html', encoding="utf-8") as f:
            lm_html = Template(f.read()).render(
                nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
                email=email, age=age, offre=offre, lm_text=lm_text
            )
        lm_pdf = pdfkit.from_string(lm_html, False, configuration=config)

        # Générer le PDF fiche de poste (simple, à partir d'un template HTML minimal)
        fiche_html = f"""
        <html>
        <head>
            <meta charset='utf-8'><title>Fiche de poste</title>
        </head>
        <body style='font-family: Segoe UI, Arial; background: #f7f8fa;'>
            <div style='background: #fff; padding:30px; border-radius: 14px; max-width:680px;margin: 20px auto;box-shadow:0 2px 18px #b2b8da33;'>
            <h1 style='color:#2b387f;'>Fiche de poste</h1>
            <pre style='font-size:1.03em;color:#344078;background:#f7f8fa;'>{fiche_text}</pre>
            </div>
        </body>
        </html>
        """
        fiche_pdf = pdfkit.from_string(fiche_html, False, configuration=config)

        # Générer les fichiers Word (DOCX)
        cv_docx = generate_docx_cv(nom, prenom, age, adresse, telephone, email, missions, qualites, cv_profile)
        lm_docx = generate_docx_lm(nom, prenom, adresse, telephone, email, age, lm_text)
        fiche_docx = generate_docx_fiche(fiche_text)

        # Sauver tous les fichiers sur disque pour download
        tmp_cv = "tmp_cv.pdf"
        tmp_lm = "tmp_lm.pdf"
        tmp_fiche = "tmp_fiche.pdf"
        tmp_cv_docx = "tmp_cv.docx"
        tmp_lm_docx = "tmp_lm.docx"
        tmp_fiche_docx = "tmp_fiche.docx"

        with open(tmp_cv, "wb") as f:
            f.write(cv_pdf)
        with open(tmp_lm, "wb") as f:
            f.write(lm_pdf)
        with open(tmp_fiche, "wb") as f:
            f.write(fiche_pdf)

        cv_docx.save(tmp_cv_docx)
        lm_docx.save(tmp_lm_docx)
        fiche_docx.save(tmp_fiche_docx)

        return render_template("result.html",
            cv_file=tmp_cv, lm_file=tmp_lm, fiche_file=tmp_fiche,
            cv_file_docx=tmp_cv_docx, lm_file_docx=tmp_lm_docx, fiche_file_docx=tmp_fiche_docx)
    return render_template("index.html")

@app.route('/download/<filename>')
def download_file(filename):
    if not os.path.exists(filename):
        return "Fichier introuvable", 404
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
