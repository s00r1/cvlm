
from flask import Flask, render_template, request, send_file, redirect, url_for
from jinja2 import Template
import pdfkit
import os
import platform
import shutil
from docx import Document
import re
import requests
import time
import tempfile
import json

app = Flask(__name__)

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
    context = {
        "nom": "", "prenom": "", "adresse": "", "telephone": "", "email": "", "age": "",
        "description": "",
        "error": ""
    }

    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        adresse = request.form.get('adresse', '').strip()
        telephone = request.form.get('telephone', '').strip()
        email = request.form.get('email', '').strip()
        age = request.form.get('age', '').strip()
        description = request.form.get('description', '').strip()

        context.update({
            "nom": nom, "prenom": prenom, "adresse": adresse,
            "telephone": telephone, "email": email, "age": age,
            "description": description
        })

        # Génération du CV avec les données utilisateur
        rendered_cv_html = render_template('cv_template.html', **context)
        cv_pdf_path = os.path.join(tempfile.gettempdir(), f"CV_{prenom}_{nom}.pdf")
        pdfkit.from_string(rendered_cv_html, cv_pdf_path, configuration=config)

        # Génération de la Lettre de Motivation avec les données utilisateur
        lettre_motivation = f"Cher recruteur, je me présente, {prenom} {nom}. Voici mes coordonnées : {adresse}, {telephone}, {email}, âgé(e) de {age} ans. {description}"
        rendered_lm_html = render_template('lm_template.html', lettre_motivation=lettre_motivation, **context)
        lm_pdf_path = os.path.join(tempfile.gettempdir(), f"LM_{prenom}_{nom}.pdf")
        pdfkit.from_string(rendered_lm_html, lm_pdf_path, configuration=config)

        # Préparation des fichiers à télécharger
        return render_template('result.html', cv_pdf=cv_pdf_path, lm_pdf=lm_pdf_path)

    return render_template('index.html', **context)

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_file(filename, as_attachment=True)
