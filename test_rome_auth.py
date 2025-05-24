import requests

CLIENT_ID = "PAR_cvlmgenerator_fc1a827d6b2f0bdfbd7895032da116528d4176a6ed6ad9b591329d0a36369d90"
CLIENT_SECRET = "c23224a1c931cb3df16630a52a6a7f476bf2549d2735ea78ef2a9f54c9b3fdf2"
TOKEN_URL = "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire"

data = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope": "api_romev1"
}

r = requests.post(TOKEN_URL, data=data)
print("Status code:", r.status_code)
print("Response:", r.text)
