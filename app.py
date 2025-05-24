from flask import Flask, render_template, request, send_file
import requests
from bs4 import BeautifulSoup
from jinja2 import Template
import pdfkit
import io
import os
import platform

app = Flask(__name__)

# Detecte OS pour wkhtmltopdf
if platform.system() == "Windows":
    WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
else:
    config = None  # Sur Linux/Railway, on laisse pdfkit trouver wkhtmltopdf

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Récupérer infos utilisateur + URL
        url = request.form['url']
        nom = request.form['nom']
        prenom = request.form['prenom']
        adresse = request.form['adresse']
        telephone = request.form['telephone']
        email = request.form['email']
        age = request.form['age']
        
        # Scraper l'offre d'emploi
        offre = scraper_offre(url)

        # Générer le CV
        with open('cv_template.html', encoding="utf-8") as f:
            cv_html = Template(f.read()).render(
                nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
                email=email, age=age, offre=offre
            )
        if config:
            cv_pdf = pdfkit.from_string(cv_html, False, configuration=config)
        else:
            cv_pdf = pdfkit.from_string(cv_html, False)
        
        # Générer la lettre de motivation
        with open('lm_template.html', encoding="utf-8") as f:
            lm_html = Template(f.read()).render(
                nom=nom, prenom=prenom, adresse=adresse, telephone=telephone,
                email=email, age=age, offre=offre
            )
        if config:
            lm_pdf = pdfkit.from_string(lm_html, False, configuration=config)
        else:
            lm_pdf = pdfkit.from_string(lm_html, False)

        # Stocker les fichiers PDF en mémoire (session, stockage temporaire, etc.)
        # Pour la démo, on va juste renvoyer la page avec des liens vers des endpoints de téléchargement
        tmp_cv = "tmp_cv.pdf"
        tmp_lm = "tmp_lm.pdf"
        with open(tmp_cv, "wb") as f:
            f.write(cv_pdf)
        with open(tmp_lm, "wb") as f:
            f.write(lm_pdf)
        
        # On passe les noms de fichiers à la page de résultats
        return render_template("result.html", cv_file=tmp_cv, lm_file=tmp_lm)
    return render_template("index.html")

@app.route('/download/<filename>')
def download_file(filename):
    # Vérifie si le fichier existe
    if not os.path.exists(filename):
        return "Fichier introuvable", 404
    return send_file(filename, as_attachment=True)

def scraper_offre(url):
    try:
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        titre = soup.title.string if soup.title else ""
        texte = ' '.join([p.get_text() for p in soup.find_all('p')])
        offre = f"{titre}\n{texte}"
        # Pour démo, limite à 500 caractères max
        if len(offre) > 500:
            offre = offre[:500] + "..."
        return offre
    except Exception as e:
        return f"Erreur lors de la récupération de l’offre : {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
