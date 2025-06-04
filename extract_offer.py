import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import socket
import ipaddress


def extract_text_from_url(url):
    parsed = urlparse(url)
    if not (parsed.scheme in ["http", "https"] and parsed.netloc):
        return "[Erreur : L’URL fournie n’est pas valide.]"
    hostname = parsed.hostname
    try:
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_link_local
            or ip_obj.is_unspecified
        ):
            return "[Erreur : URL non autorisée.]"
    except Exception as e:
        return f"[Erreur lors de la résolution DNS : {e}]"

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; OfferScraper/1.0; +https://tonsite.com)"
            )
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(
            ["script", "style", "nav", "footer", "header", "aside", "form"]
        ):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        cleaned_text = "\n".join(lines)
        if len(cleaned_text) < 200:
            return (
                "[Erreur : Impossible d’extraire correctement l’offre d’emploi "
                "(texte trop court). "
                "Essayez de la copier/coller manuellement.]"
            )
        if len(cleaned_text) > 20000:
            return (
                "[Erreur : Texte extrait trop volumineux ou bruité. "
                "Veuillez copier/coller manuellement l’offre.]"
            )
        return cleaned_text
    except Exception as e:
        return f"[Erreur lors de la récupération de la page : {e}]"
