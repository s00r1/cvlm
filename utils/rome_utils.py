
import requests

def get_rome_data(rome_code):
    if not rome_code:
        return {}
    token = "YOUR_TOKEN"  # À remplacer dynamiquement si besoin
    headers = {
        "Authorization": f"Bearer {token}"
    }
    url = f"https://api.pole-emploi.io/partenaire/rome/v1/metiers/{rome_code}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return {}
