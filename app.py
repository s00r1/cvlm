from flask import Flask, render_template, request, send_file
from jinja2 import Template
import pdfkit
import io
import os
import platform
import re
import shutil

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

        tmp_cv = "tmp_cv.pdf"
        tmp_lm = "tmp_lm.pdf"
        with open(tmp_cv, "wb") as f:
            f.write(cv_pdf)
        with open(tmp_lm, "wb") as f:
            f.write(lm_pdf)

        return render_template("result.html", cv_file=tmp_cv, lm_file=tmp_lm)
    return render_template("index.html")

@app.route('/download/<filename>')
def download_file(filename):
    if not os.path.exists(filename):
        return "Fichier introuvable", 404
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
