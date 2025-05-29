# prompts.py

SYSTEM_PROMPT = "Tu es un assistant RH expert, spécialiste du recrutement en France."

PROMPT_PARSE_CV = """
Lis attentivement le texte suivant extrait d’un CV PDF ou DOCX. Trie les informations dans ce JSON, section par section, sans jamais inventer :

{
  "nom": "...",
  "prenom": "...",
  "adresse": "...",
  "telephone": "...",
  "email": "...",
  "age": "...",
  "profil": "...",
  "competences": ["...", "..."],
  "experiences": ["...", "..."],
  "formations": ["...", "..."],
  "autres": ["...", "..."]
}

Si tu ne trouves pas une section, laisse-la vide, mais structure toujours le JSON comme ci-dessus.

TEXTE DU CV À PARSER :
\"\"\"{cv_uploaded_text}\"\"\"
"""

PROMPT_LM_CV = """
Voici le parsing structuré du CV du candidat, issu de l’étape précédente :
{cv_data}

Voici l'offre d'emploi à laquelle il postule :
\"\"\"{description}\"\"\"

1. Rédige une lettre de motivation personnalisée et professionnelle adaptée à l'offre et au parcours du candidat (exploite le maximum d’infos utiles, mets en avant les expériences ou compétences transversales si besoin).
2. Génère le contenu d’un CV adapté à l’offre, en sélectionnant :
   - Un paragraphe de profil synthétique (adapté au poste)
   - Les compétences les plus pertinentes (croisées entre CV et offre)
   - Les expériences professionnelles les plus adaptées, sous forme de bullet points (intitulé, entreprise, dates, mission principale)
   - Les formations principales
   - Autres infos utiles

Rends ce JSON strictement :
{
  "lettre_motivation": "....",
  "cv_adapte": {
    "profil": "...",
    "competences": ["...", "..."],
    "experiences": ["...", "..."],
    "formations": ["...", "..."],
    "autres": ["...", "..."]
  }
}
"""

PROMPT_FICHE_POSTE = """
Lis attentivement l'offre d'emploi suivante et extrait-en les éléments principaux pour générer une fiche de poste structurée, en remplissant strictement ce JSON (sans inventer) :

{
  "titre": "...",
  "employeur": "...",
  "ville": "...",
  "salaire": "...",
  "type_contrat": "...",
  "missions": ["...", "..."],
  "competences": ["...", "..."],
  "avantages": ["...", "..."],
  "savoir_etre": ["...", "..."],
  "autres": ["..."]
}

Offre à analyser :
\"\"\"{description}\"\"\"
"""

PROMPT_FIELDS = """
Voici les infos saisies par le candidat :

Nom : {nom}
Prénom : {prenom}
Adresse : {adresse}
Téléphone : {telephone}
Email : {email}
Âge : {age}

Expériences professionnelles :
{xp_poste}
Entreprises : {xp_entreprise}
Lieux : {xp_lieu}
Dates début : {xp_debut}
Dates fin : {xp_fin}

Diplômes : {dip_titre}
Lieux : {dip_lieu}
Dates : {dip_date}

Voici l'offre d'emploi :
\"\"\"{description}\"\"\"

Génère une lettre de motivation adaptée à l’offre et au parcours, puis un CV adapté en JSON :

{
  "lettre_motivation": "...",
  "cv_adapte": {
    "profil": "...",
    "competences": ["...", "..."],
    "experiences": ["...", "..."],
    "formations": ["...", "..."],
    "autres": ["...", "..."]
  }
}
"""
