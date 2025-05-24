from flask import Flask, render_template, request, send_file, render_template_string, Markup
import requests
import os
import pdfkit
from docx import Document
import shutil
import json
import markdown2

GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

def find_wkhtmltopdf():
    return shutil.which("wkhtmltopdf")

if os.name == "nt":
    config = pdfkit.configuration(wkhtmltopdf=r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe")
else:
    wkhtmltopdf_path = find_wkhtmltopdf()
    if wkhtmltopdf_path:
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    else:
        config = None

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

def make_docx_cv(nom, prenom, cv):
    doc = Document()
    doc.add_heading(f"{prenom} {nom}", 0)
    doc.add_heading("Profil professionnel", level=1)
    doc.add_paragraph(cv.get("profil", ""))
    doc.add_heading("Compétences adaptées au poste", level=1)
    for skill in cv.get("competences_croisees", []):
        doc.add_paragraph(skill, style='List Bullet')
    doc.add_heading("Expériences professionnelles", level=1)
    for exp in cv.get("experiences", []):
        doc.add_paragraph(exp, style='List Bullet')
    doc.add_heading("Formations & diplômes", level=1)
    for f in cv.get("formations", []):
        doc.add_paragraph(f, style='List Bullet')
    doc.save("tmp_cv.docx")

def make_docx_lm(nom, prenom, lm):
    doc = Document()
    doc.add_heading("Lettre de motivation", 0)
    doc.add_paragraph(f"{prenom} {nom}\n")
    for line in lm.split('\n'):
        doc.add_paragraph(line)
    doc.save("tmp_lm.docx")

def make_docx_fiche(fiche_poste):
    doc = Document()
    doc.add_heading(fiche_poste.get("titre", ""), 0)
    doc.add_paragraph(f"Employeur : {fiche_poste.get('employeur','')}")
    doc.add_paragraph(f"Ville : {fiche_poste.get('ville','')}")
    doc.add_paragraph(f"Salaire : {fiche_poste.get('salaire','')}")
    doc.add_paragraph(f"Type de contrat : {fiche_poste.get('type_contrat','')}")
    doc.add_heading("Missions principales", level=1)
    for m in fiche_poste.get("missions", []):
        doc.add_paragraph(m, style='List Bullet')
    doc.add_heading("Compétences requises", level=1)
    for c in fiche_poste.get("competences", []):
        doc.add_paragraph(c, style='List Bullet')
    doc.add_heading("Savoir-être", level=1)
    for s in fiche_poste.get("savoir_etre", []):
        doc.add_paragraph(s, style='List Bullet')
    doc.add_heading("Avantages", level=1)
    for a in fiche_poste.get("avantages", []):
        doc.add_paragraph(a, style='List Bullet')
    doc.add_heading("Autres informations", level=1)
    for x in fiche_poste.get("autres", []):
        doc.add_paragraph(x, style='List Bullet')
    doc.save("tmp_fiche.docx")

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    fiche_poste = cv = lettre_motivation = {}
    error = ""
    fiche_preview = cv_preview = lm_preview = ""
    if request.method == "POST":
        nom = request.form.get("nom", "")
        prenom = request.form.get("prenom", "")
        adresse = request.form.get("adresse", "")
        telephone = request.form.get("telephone", "")
        email = request.form.get("email", "")
        age = request.form.get("age", "")
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
        dip_titre = request.form.getlist("dip_titre")
        dip_lieu = request.form.getlist("dip_lieu")
        dip_date = request.form.getlist("dip_date")
        diplomes = []
        for titre, lieu, date in zip(dip_titre, dip_lieu, dip_date):
            if titre and lieu and date:
                diplomes.append(f"{titre} obtenu à {lieu} ({date})")
        diplomes_user = "; ".join(diplomes) if diplomes else "Non renseigné"
        offre = request.form.get("description", "").strip()

        # ------------ PROMPT JSON PRO --------------
        prompt = f"""
Tu es un assistant RH expert. Lis l'offre et les données du candidat. Ne jamais inventer.

Renvoie STRICTEMENT ce JSON :

{{
  "fiche_poste": {{
    "titre": "...",
    "employeur": "...",
    "ville": "...",
    "salaire": "...",
    "type_contrat": "...",
    "missions": [...],
    "competences": [...],
    "avantages": [...],
    "savoir_etre": [...],
    "autres": [...]
  }},
  "cv": {{
    "profil": "...",
    "competences_croisees": [...],
    "experiences": [...],
    "formations": [...],
    "autres": []
  }},
  "lettre_motivation": "texte complet ultra-adapté à l'offre, au profil, en français pro"
}}

Expériences : {experiences_user}
Diplômes : {diplomes_user}

OFFRE D'EMPLOI :
\"\"\"
{offre}
\"\"\"
        """
        try:
            result = ask_groq(prompt)
            # Cherche le JSON dans la réponse
            json_start = result.index("{")
            data = json.loads(result[json_start:])
            fiche_poste = data.get("fiche_poste", {})
            cv = data.get("cv", {})
            lettre_motivation = data.get("lettre_motivation", "")
        except Exception as e:
            error = f"Erreur IA ou parsing JSON : {e}"
            fiche_poste = cv = {}
            lettre_motivation = ""

        # Rendu preview HTML clean (markdown2 gère listes/bold, etc)
        fiche_preview = Markup(markdown2.markdown(f"""
### {fiche_poste.get('titre','')}
**Employeur :** {fiche_poste.get('employeur','')}  
**Ville :** {fiche_poste.get('ville','')}  
**Salaire :** {fiche_poste.get('salaire','')}  
**Type de contrat :** {fiche_poste.get('type_contrat','')}

#### Missions principales
""" + "\n".join(f"- {x}" for x in fiche_poste.get("missions", [])) + """

#### Compétences requises
""" + "\n".join(f"- {x}" for x in fiche_poste.get("competences", [])) + """

#### Savoir-être
""" + "\n".join(f"- {x}" for x in fiche_poste.get("savoir_etre", [])) + """

#### Avantages
""" + "\n".join(f"- {x}" for x in fiche_poste.get("avantages", [])) + """

#### Autres informations
""" + "\n".join(f"- {x}" for x in fiche_poste.get("autres", []))
        ))

        cv_preview = Markup(markdown2.markdown(f"""
**Profil**  
{cv.get('profil','')}

**Compétences adaptées au poste :**  
""" + ", ".join(cv.get('competences_croisees', [])) + """

**Expériences professionnelles :**  
""" + "\n".join(f"- {x}" for x in cv.get('experiences', [])) + """

**Formations :**  
""" + "\n".join(f"- {x}" for x in cv.get('formations', []))
        ))

        lm_preview = Markup(markdown2.markdown(lettre_motivation))

        # Rendu PDF/Word PRO
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        with open(os.path.join(template_dir, "cv_template.html"), encoding="utf-8") as f:
            cv_html = render_template_string(f.read(), nom=nom, prenom=prenom, cv=cv)
        with open(os.path.join(template_dir, "fiche_poste_template.html"), encoding="utf-8") as f:
            fiche_html = render_template_string(f.read(), fiche_poste=fiche_poste)
        with open(os.path.join(template_dir, "lm_template.html"), encoding="utf-8") as f:
            lm_html = render_template_string(f.read(), nom=nom, prenom=prenom, lettre_motivation=lettre_motivation)

        if config:
            pdfkit.from_string(cv_html, "tmp_cv.pdf", configuration=config)
            pdfkit.from_string(lm_html, "tmp_lm.pdf", configuration=config)
            pdfkit.from_string(fiche_html, "tmp_fiche.pdf", configuration=config)

        make_docx_cv(nom, prenom, cv)
        make_docx_lm(nom, prenom, lettre_motivation)
        make_docx_fiche(fiche_poste)

        return render_template(
            "result.html",
            fiche_file="tmp_fiche.pdf", fiche_file_docx="tmp_fiche.docx",
            cv_file="tmp_cv.pdf", cv_file_docx="tmp_cv.docx",
            lm_file="tmp_lm.pdf", lm_file_docx="tmp_lm.docx",
            error=error,
            fiche_preview=fiche_preview,
            cv_preview=cv_preview,
            lm_preview=lm_preview
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
