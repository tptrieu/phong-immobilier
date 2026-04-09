# =============================================================================
# config.py — Configuration centrale du système de réponse automatique
# =============================================================================

import os

# --- Comptes Gmail -----------------------------------------------------------

ACCOUNTS = {
    "centris": {
        "email": "phong@tptrieu.com",
        "token_file": "token_centris.json",
        "sender_filter": ["do-not-reply@centris.ca", "nepasrepondre@centris.ca"],
        "display_name": "Phong Trieu | Courtier immobilier",
    },
    "remax": {
        "email": "thanhphong.trieu@remax-quebec.com",
        "token_file": "token_remax.json",
        "sender_filter": "noreply@remax-quebec.com",
        "display_name": "Phong Trieu | RE/MAX",
    },
    "realtor": {
        "email": "phong@tptrieu.com",
        "token_file": "token_centris.json",   # même compte Gmail que Centris
        "sender_filter": "Lead@realtor.ca",
        "display_name": "Phong Trieu | Courtier immobilier",
        "template": "centris",                # réutilise centris_fr.txt / centris_en.txt
    },
}

# --- Fichier de suivi des emails traités ------------------------------------

PROCESSED_FILE = "processed_emails.json"

# --- Credentials OAuth2 ------------------------------------------------------

CREDENTIALS_FILE = "credentials.json"

# --- Scopes Gmail ------------------------------------------------------------

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",   # pour marquer comme lu / ajouter label
    "https://www.googleapis.com/auth/spreadsheets",   # pour Google Sheets
]

# --- Google Sheets -----------------------------------------------------------

SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID", "")

# --- Paramètres de traitement ------------------------------------------------

# Nombre de messages à analyser par exécution (les plus récents non lus)
MAX_EMAILS_PER_RUN = 20

# Label Gmail appliqué aux emails traités (créé automatiquement s'il n'existe pas)
PROCESSED_LABEL = "Auto-Répondu"

# --- Détection de langue -----------------------------------------------------

# Mots-clés qui indiquent clairement le français
FRENCH_KEYWORDS = [
    "bonjour", "salut", "merci", "propriété", "maison", "appartement",
    "prix", "chambre", "salle", "cuisine", "garage", "visiter", "visite",
    "disponible", "intéressé", "intéressée", "informations", "renseignements",
    "cher", "chère", "monsieur", "madame", "je", "nous", "vous", "est", "sont",
    "pour", "avec", "dans", "sur", "cette", "votre", "notre",
]

# Mots-clés qui indiquent clairement l'anglais
ENGLISH_KEYWORDS = [
    "hello", "hi", "thanks", "thank", "property", "house", "condo",
    "apartment", "price", "bedroom", "bathroom", "kitchen", "garage",
    "visit", "viewing", "available", "interested", "information",
    "dear", "sir", "madam", "i ", "we ", "you ", "is ", "are ",
    "for ", "with ", "in ", "on ", "this ", "your ", "our ",
]
