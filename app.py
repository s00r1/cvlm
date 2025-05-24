from flask import Flask, render_template, request, send_file
import requests
import os
import pdfkit
from docx import Document
import shutil

GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# PDFkit config auto
def find_wkhtmltopdf():
    return shutil.which("wkhtmltopdf")

if os.name == "nt":
    config = pdfkit.configuration(wkhtmltopdf=r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe")
else:
    wkhtmltopdf_path = find_wkhtmltopdf()
    if wkhtmltopdf_path:
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    else:
        config = None  # PDF export désactivé si binaire absent

def ask_groq(prompt, model=GROQ_MODEL):
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
        "temperature": 0.3
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    r = requests.post(GROQ_URL, json=data, headers=headers, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def make_docx_cv(nom, prenom, cv_text):
    doc = Document()
    doc.add_heading(f"{prenom} {nom}", 0)
    doc.add_heading("Profil professionnel", level=1)
    for line in cv_text.split('\n'):
        doc.add_paragraph(line)
    doc.save("tmp_cv.docx")

def make_docx_lm(nom, prenom, lm_text):
    doc = Document()
    doc.add_heading("Lettre de motivation", 0)
    doc.add_paragraph(f"{prenom} {nom}\n")
    for line in lm_text.split('\n'):
        doc.add_paragraph(line)
    doc.save("tmp_lm.docx")

def make_docx_fiche(fiche_text):
    doc = Document()
    doc.add_heading("Fiche de poste", 0)
    for line in fiche_text.split('\n'):
        doc.add_paragraph(line)
    doc.save("tmp_fiche.docx")

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    fiche_text = cv_text = lm_text = ""
    error = ""
    if request.method == "POST":
        # Champs utilisateur
        nom = request.form.get("nom", "")
        prenom = request.form.get("prenom", "")
        adresse = request.form.get("adresse", "")
        telephone = request.form.get("telephone", "")
        email = request.form.get("email", "")
        age = request.form.get("age", "")

        # Expériences pro
        xp_poste = request.form.getlist("xp_poste")
        xp_entreprise = request.form.getlist("xp_entreprise")
        xp_lieu = request.form.getlist("xp_lieu")
        xp_debut = request.form.getlist("xp_debut")
        xp_fin = request.form.getlist("xp_fin")
        experiences = []
        for poste, ent, lieu, debut, fin in zip(xp_poste, xp_entreprise, xp_lieu, xp_debut, xp_fin):
            if poste and ent and lieu and debut and fin:
                experiences.append(f"{poste} chez {ent}, à {lieu} ({debut} – {fin})")
        experiences_user = "; ".join(experiences) if experiences else "Non renseigné"

        # Diplômes
        dip_titre = request.form.getlist("dip_titre")
        dip_lieu = request.form.getlist("dip_lieu")
        dip_date = request.form.getlist("dip_date")
        diplomes = []
        for titre, lieu, date in zip(dip_titre, dip_lieu, dip_date):
            if titre and lieu and date:
                diplomes.append(f"{titre} obtenu à {lieu} ({date})")
        diplomes_user = "; ".join(diplomes) if diplomes else "Non renseigné"

        # Offre brute
        offre = request.form.get("description", "").strip()

        # Prompt IA
        prompt = f"""
Tu es un assistant RH expert, précis, créatif et synthétique.

1. À partir de l’offre d’emploi suivante, **extrait et liste toutes les informations utiles et significatives** : 
- Titre du poste, employeur, localisation, salaire, type de contrat, date(s), missions principales, tâches spécifiques, compétences attendues, savoir-être recherchés, avantages, conditions de travail, primes, progression, formation, outils/technologies, langues, horaires, contexte d’entreprise, contact, tout détail notable (même non standard).
- Si une information n’existe pas dans l’offre, ne l’invente pas et ne la complète pas. Classe chaque info dans un titre clair, et ajoute une section “Autres informations importantes” si tu repères un détail clé non listé ci-dessus.

2. Structure tout cela dans une **fiche de poste synthétique** en utilisant des titres et des listes à puces claires.

3. **Voici les expériences professionnelles de l’utilisateur** : {experiences_user}
4. **Voici ses diplômes et formations** : {diplomes_user}

5. **À partir de toutes ces données :**
- Génère un **profil professionnel** à placer en haut du CV, personnalisé à l’offre, qui met en valeur la cohérence entre le parcours, les compétences de l’utilisateur et le poste visé (n’hésite pas à déceler les compétences transférables).
- Rédige une **lettre de motivation complète, percutante et convaincante**, ultra-adaptée à l’offre ET au profil utilisateur, en valorisant chaque élément pertinent (parcours, diplômes, adéquation avec les attentes du poste, atouts pour l’employeur).

6. Ta réponse doit être en markdown, avec ce format strict :

===FICHE===
[fiche synthétique : chaque info extraite sous un titre, listes à puces pour missions/compétences, aucune invention]
===CV===
[profil CV adapté, intégrant expériences/diplômes, crédible et personnalisé]
===LM===
[lettre de motivation, ciblée, argumentée, en bon français professionnel]

**OFFRE D’EMPLOI** :
\"\"\"
{offre}
\"\"\"
"""

        try:
            result = ask_groq(prompt)
            fiche_text = cv_text = lm_text = ""
            if "===FICHE===" in result and "===CV===" in result and "===LM===" in result:
                fiche_text = result.split("===FICHE===")[1].split("===CV===")[0].strip()
                cv_text = result.split("===CV===")[1].split("===LM===")[0].strip()
                lm_text = result.split("===LM===")[1].strip()
            else:
                fiche_text = result  # fallback
        except Exception as e:
            error = f"Erreur IA : {e}"

        # Génération PDF/Word (utilise tes modèles ou simplement le texte, ici version simple)
        with open("cv_template.html", encoding="utf-8") as f:
            cv_html = render_template_string(f.read(), nom=nom, prenom=prenom, cv_text=cv_text)
        with open("lm_template.html", encoding="utf-8") as f:
            lm_html = render_template_string(f.read(), nom=nom, prenom=prenom, lm_text=lm_text)
        with open("fiche_poste_template.html", encoding="utf-8") as f:
            fiche_html = render_template_string(f.read(), fiche_text=fiche_text)

        if config:
            pdfkit.from_string(cv_html, "tmp_cv.pdf", configuration=config)
            pdfkit.from_string(lm_html, "tmp_lm.pdf", configuration=config)
            pdfkit.from_string(fiche_html, "tmp_fiche.pdf", configuration=config)

        make_docx_cv(nom, prenom, cv_text)
        make_docx_lm(nom, prenom, lm_text)
        make_docx_fiche(fiche_text)

        return render_template(
            "result.html",
            fiche_file="tmp_fiche.pdf", fiche_file_docx="tmp_fiche.docx",
            cv_file="tmp_cv.pdf", cv_file_docx="tmp_cv.docx",
            lm_file="tmp_lm.pdf", lm_file_docx="tmp_lm.docx",
            error=error
        )
    return render_template("index.html")

@app.route('/download/<filename>')
def download_file(filename):
    if not os.path.exists(filename):
        return "Fichier introuvable", 404
    return send_file(filename, as_attachment=True)

from flask import render_template_string

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
