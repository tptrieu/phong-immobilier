# =============================================================================
# auth.py — Authentification OAuth2 Gmail
# =============================================================================

import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import CREDENTIALS_FILE, GMAIL_SCOPES


def get_gmail_service(token_file: str, email: str):
    """
    Retourne un service Gmail authentifié pour le compte donné.
    Lance le flux OAuth2 la première fois (ouvre le navigateur).
    Les tokens sont sauvegardés dans token_file pour les exécutions suivantes.
    """
    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, GMAIL_SCOPES)

    # Renouveler si expiré
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds, token_file)

    # Premier login — ouvre le navigateur
    elif not creds or not creds.valid:
        print(f"\n[AUTH] Connexion requise pour : {email}")
        print(f"       Le navigateur va s'ouvrir. Connectez-vous avec ce compte.")
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
        _save_token(creds, token_file)
        print(f"[AUTH] Token sauvegardé dans {token_file}")

    service = build("gmail", "v1", credentials=creds)
    return service


def _save_token(creds: Credentials, token_file: str):
    with open(token_file, "w") as f:
        f.write(creds.to_json())
