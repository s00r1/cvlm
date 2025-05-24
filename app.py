from flask import Flask, render_template, request, send_file
import requests
from bs4 import BeautifulSoup
from jinja2 import Template
import pdfkit
import io
import os
import platform
import re
import shutil

app = Flask(__name__)

# --- Génération intelligente de texte pour le CV et la LM ---
def generer_cv_text(nom, prenom, age, offre):
    mots = re.findall(r'\b\w+\b', offre.lower())
    freq = {}
    for mot in mots:
        if len(mot) > 3:
            freq[mot] = freq.get(mot, 0) + 1
    top = sorted(freq, key=freq.get, reverse=True)[:3]
    skills = ', '.join(top)
    return f"Je m'appelle {prenom} {nom}, j'ai {age} ans. Passionné(e) par les domaines suivants : {skills}. Motivé(e) et rigoureux(se), je souhaite apporter mon énergie et mon sérieux à votre entreprise."

def generer_lm_text(nom, prenom, offre):
    titre = offre.split('\n')[0][:70]
    return (
        f"Madame, Monsieur,\n\n"
        f"Je vous adresse ma candidature pour le poste de '{titre}'. "
        f"Après avoir pris connaissance de votre annonce, je suis convaincu(e) que mes qualités humaines et mon engagement correspondent à vos attentes. Je suis motivé(e) à rejoindre votre équipe et à contribuer activement à vos projets.\n\n"
        f"Je me tiens à votre disposition pour un entretien.\n\n"
        f"Cordialement,\n{prenom} {nom}"
    )

# --- pdfkit config OS-aware ---

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
        raise RuntimeError("wkhtmltopdf non trouvé sur le système Railway ! Vérifie l'installation Nixpacks/variable d'environnement.")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        nom = request.form['nom']
        prenom = request.form['prenom']
        adresse = request.form['adresse']
        telephone = request.form['telephone']
        email = request.form['email']
        age = request.form['age']
        
        offre = scraper_offre(url)

        # --- Génération IA locale ---
        cv_profile = generer_cv_text(nom, prenom, age, offre)
        lm_text = generer_lm_text(nom, prenom, offre)

        # Générer le CV
        with open('cv_template.html', encoding="utf-8") as f:
            cv_html = Template(f.read()).render(
                nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
                email=email, age=age, offre=offre, cv_profile=cv_profile
            )
        cv_pdf = pdfkit.from_string(cv_html, False, configuration=config)
        
        # Générer la lettre de motivation
        with open('lm_template.html', encoding="utf-8") as f:
            lm_html = Template(f.read()).render(
                nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
                email=email, age=age, offre=offre, lm_text=lm_text
            )
        lm_pdf = pdfkit.from_string(lm_html, False, configuration=config)

        # Stocker les fichiers PDF temporairement
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

def scraper_offre(url):
    try:
        r = requests.get(url, timeout=5, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        soup = BeautifulSoup(r.text, 'html.parser')
        titre = soup.title.string if soup.title else "Offre d'emploi"
        texte = ' '.join([p.get_text() for p in soup.find_all('p')]) or "(Impossible de récupérer le texte de l'annonce, le site est protégé.)"
        offre = f"{titre}\n{texte}"
        if len(offre) > 500:
            offre = offre[:500] + "..."
        return offre
    except Exception as e:
        return f"Erreur lors de la récupération de l’offre : {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
