import os
import re
import requests
import json
import logging

logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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
            {"role": "system", "content": "Tu es un assistant RH expert, spécialiste du recrutement en France."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 2800
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=80)
        j = resp.json()
        logger.debug("Réponse brute GROQ: %s", j)
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
    """
    Extrait le premier bloc JSON correct d'un texte, même s'il est entouré de markdown, texte, etc.
    """
    if not text:
        return None
    # 1. Cherche bloc markdown ```json ... ```
    matches = re.findall(r'```json\s*([\s\S]+?)```', text)
    for block in matches:
        try:
            return json.loads(block)
        except Exception:
            continue
    # 2. Cherche bloc markdown ``` ... ```
    matches = re.findall(r'```([\s\S]+?)```', text)
    for block in matches:
        try:
            return json.loads(block)
        except Exception:
            continue
    # 3. Cherche premier bloc {...}
    matches = re.findall(r'({[\s\S]+?})', text)
    for block in matches:
        try:
            return json.loads(block)
        except Exception:
            continue
    # 4. Nettoyage ultime (enlève les \n, \r, remplace ' par " )
    clean = re.sub(r'```(?:json)?', '', text, flags=re.IGNORECASE)
    clean = re.sub(r'```', '', clean)
    m = re.search(r'(\{[\s\S]+\})', clean)
    if not m:
        return None
    json_str = m.group(1)
    try:
        return json.loads(json_str)
    except Exception:
        json_str_clean = json_str.replace('\n', '').replace('\r', '')
        try:
            return json.loads(json_str_clean)
        except Exception:
            json_str_clean2 = json_str_clean.replace("'", '"')
            try:
                return json.loads(json_str_clean2)
            except Exception:
                return None
