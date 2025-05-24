import requests
import time

CLIENT_ID = "PAR_cvlmgenerator_fc1a827d6b2f0bdfbd7895032da116528d4176a6ed6ad9b591329d0a36369d90"
CLIENT_SECRET = "c23224a1c931cb3df16630a52a6a7f476bf2549d2735ea78ef2a9f54c9b3fdf2"
TOKEN_URL = "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire"
ROME_API_URL = "https://api.pole-emploi.io/partenaire/rome/v1/metiers"

class RomeAPIClient:
    def __init__(self):
        self.token = None
        self.token_expiry = 0

    def get_token(self):
        # Si token existe et est encore valide (expire dans +5 min), on le réutilise
        if self.token and time.time() < self.token_expiry - 300:
            return self.token
        # Sinon, on en demande un nouveau
        data = {
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "api_romev1"
        }
        r = requests.post(TOKEN_URL, data=data)
        if r.status_code != 200:
            raise Exception(f"Erreur auth API ROME : {r.status_code} {r.text}")
        resp = r.json()
        self.token = resp['access_token']
        self.token_expiry = time.time() + int(resp['expires_in'])
        return self.token

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.get_token()}"
        }

    def guess_rome_code(self, job_title):
        params = {"libelle": job_title}
        r = requests.get(ROME_API_URL, headers=self.get_headers(), params=params)
        if r.status_code == 200 and r.json():
            metiers = r.json()
            if metiers:
                code = metiers[0].get("code")
                libelle = metiers[0].get("libelle")
                return code, libelle
        return None, None

    def fetch_rome_details(self, code):
        url = f"https://api.pole-emploi.io/partenaire/rome/v1/metiers/{code}"
        r = requests.get(url, headers=self.get_headers())
        if r.status_code == 200 and r.json():
            return r.json()
        return None

# On crée une instance globale pour le projet
rome_api_client = RomeAPIClient()

# Facilité d'import dans app.py :
def guess_rome_code(job_title):
    return rome_api_client.guess_rome_code(job_title)

def fetch_rome_details(code):
    return rome_api_client.fetch_rome_details(code)
