from flask import Flask, render_template, request, send_file
from jinja2 import Template
import pdfkit
import io
import os
import platform
import re
import shutil

app = Flask(__name__)

def generer_cv_text(nom, prenom, age, offre):
    mots = re.findall(r'\b\w+\b', offre.lower())
    freq = {}
    for mot in mots:
        if len(mot) > 3:
            freq[mot] = freq.get(mot, 0) + 1
    top = sorted(freq, key=freq.get, reverse=True)[:5]
    skills = ', '.join(top)
    return f"Je m'appelle {prenom} {nom}, j'ai {age} ans. Je possède des qualités et un intérêt marqué pour : {skills}. Sérieux(se), motivé(e), je souhaite mettre mes compétences et mon énergie au service de votre entreprise."

def generer_lm_text(nom, prenom, offre):
    titre = offre.split('\n')[0][:70]
    return (
        f"Madame, Monsieur,\n\n"
        f"Je vous adresse ma candidature pour le poste de « {titre} ».\n"
        f"Votre annonce a retenu toute mon attention. Je pense réunir les qualités nécessaires pour m’intégrer rapidement à votre équipe, et je suis convaincu(e) que mon engagement, mon sérieux et ma motivation correspondent à vos attentes.\n\n"
        f"Je serais ravi(e) de pouvoir vous exposer ma motivation lors d’un entretien.\n\n"
        f"Cordialement,\n{prenom} {nom}"
    )

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

        cv_profile = generer_cv_text(nom, prenom, age, offre)
        lm_text = generer_lm_text(nom, prenom, offre)

        with open('cv_template.html', encoding="utf-8") as f:
            cv_html = Template(f.read()).render(
                nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
                email=email, age=age, offre=offre, cv_profile=cv_profile
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
