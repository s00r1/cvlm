import os
import re
import requests
import json
from prompts import SYSTEM_PROMPT  # 👈 Ajout ici

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY non défini dans les variables d'environnement !")

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

def ask_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    data = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},  # 👈 ICI
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 2800
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=80)
        j = resp.json()
        print("Réponse brute GROQ:", j)
        if not isinstance(j, dict) or "choices" not in j or not j["choices"]:
            error_msg = f"Erreur d'appel à l'IA : réponse inattendue ou vide. Détail : {j}"
            print(error_msg)
            return error_msg
        return j["choices"][0]["message"]["content"]
    except Exception as e:
        error_msg = f"Erreur lors de la requête IA : {str(e)}"
        print(error_msg)
        return error_msg

def extract_first_json(text):
    m = re.search(r'(\{[\s\S]+\})', text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        text_clean = m.group(1).replace('\n', '').replace('\r', '')
        try:
            return json.loads(text_clean)
        except Exception:
            return None
