
from flask import Flask, render_template, request, send_file
import requests
import json
import os
from utils.rome_utils import get_rome_data

app = Flask(__name__)

# Credentials (à sécuriser dans une vraie prod)
CLIENT_ID = "VOTRE_CLIENT_ID"
CLIENT_SECRET = "VOTRE_CLIENT_SECRET"
TOKEN_URL = "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire"

# Récupère un token d'accès
def get_token():
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "api_offresdemploiv2 o2dsoffre"
    }
    headers = { "Content-Type": "application/x-www-form-urlencoded" }
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    return response.json()["access_token"]

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    mots_cles = request.form["mots_cles"]
    commune = request.form["commune"]
    distance = request.form["distance"]

    token = get_token()
    headers = { "Authorization": f"Bearer {token}" }

    params = {
        "motsCles": mots_cles,
        "commune": commune,
        "distance": distance,
        "range": "0-9"
    }

    response = requests.get("https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search", headers=headers, params=params)
    offres = response.json().get("resultats", [])

    return render_template("index.html", offres=offres)

@app.route("/generate", methods=["POST"])
def generate():
    offre_id = request.form["offre_id"]
    token = get_token()
    headers = { "Authorization": f"Bearer {token}" }

    response = requests.get(f"https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/{offre_id}", headers=headers)
    data = response.json()

    intitule = data.get("intitule", "Offre")
    lieu = data.get("lieuTravail", {}).get("libelle", "Non précisé")
    contrat = data.get("typeContrat", "Non précisé")
    salaire = data.get("salaire", {}).get("libelle", "Non précisé")
    rome_code = data.get("romeCode")

    rome_infos = get_rome_data(rome_code) if rome_code else {}

    # Tu peux ici générer les fichiers PDF avec reportlab, etc...

    return render_template("result.html", offre=data, rome=rome_infos)

if __name__ == "__main__":
    app.run(debug=True)
