# =============================================================================
# auth.py — Authentification OAuth2 Gmail
# Supporte deux modes :
#   - Local  : lit credentials.json + token_*.json (développement)
#   - Serveur: lit GOOGLE_CREDENTIALS_JSON + GMAIL_TOKEN_* depuis l'environnement
# =============================================================================

import os
import json
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import CREDENTIALS_FILE, GMAIL_SCOPES

# Mapping token_file → variable d'environnement
_TOKEN_ENV_MAP = {
    "token_centris.json": "GMAIL_TOKEN_CENTRIS",
    "token_remax.json":   "GMAIL_TOKEN_REMAX",
}


def get_gmail_service(token_file: str, email: str):
    """
    Retourne un service Gmail authentifié.

    Ordre de résolution des credentials :
    1. Variable d'environnement GMAIL_TOKEN_<NOM> (Railway / serveur)
    2. Fichier local token_*.json                 (Mac / développement)
    3. Flux OAuth2 interactif                     (premier lancement local seulement)
    """
    creds = _load_token(token_file)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token_if_local(creds, token_file)

    elif not creds or not creds.valid:
        if _is_server_env():
            raise RuntimeError(
                f"[AUTH] Aucun token valide pour {email}. "
                f"Définir la variable d'environnement {_TOKEN_ENV_MAP.get(token_file, 'GMAIL_TOKEN_?')}."
            )
        # Local : ouvrir le navigateur
        print(f"\n[AUTH] Connexion requise pour : {email}")
        print(f"       Le navigateur va s'ouvrir. Connectez-vous avec ce compte.")
        creds_info = _load_client_secrets()
        flow = InstalledAppFlow.from_client_config(creds_info, GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
        _save_token_if_local(creds, token_file)
        print(f"[AUTH] Token sauvegardé dans {token_file}")

    return build("gmail", "v1", credentials=creds)


# -----------------------------------------------------------------------------
# Helpers privés
# -----------------------------------------------------------------------------

def _load_token(token_file: str) -> Credentials | None:
    """Charge le token depuis l'env var (base64) en priorité, sinon depuis le fichier."""
    env_var = _TOKEN_ENV_MAP.get(token_file)
    if env_var:
        token_b64 = os.environ.get(env_var)
        if token_b64:
            token_json = _b64_decode(token_b64)
            return Credentials.from_authorized_user_info(json.loads(token_json), GMAIL_SCOPES)

    if os.path.exists(token_file):
        return Credentials.from_authorized_user_file(token_file, GMAIL_SCOPES)

    return None


def _load_client_secrets() -> dict:
    """Charge les secrets OAuth2 depuis l'env var (base64) ou le fichier local."""
    creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_b64:
        return json.loads(_b64_decode(creds_b64))
    with open(CREDENTIALS_FILE, "r") as f:
        return json.load(f)


def _b64_decode(value: str) -> str:
    """Décode une valeur base64, tolère le padding manquant."""
    padded = value.strip() + "=" * (-len(value.strip()) % 4)
    return base64.b64decode(padded).decode("utf-8")


def _save_token_if_local(creds: Credentials, token_file: str):
    """Sauvegarde le token seulement en local (inutile sur Railway)."""
    if not _is_server_env():
        with open(token_file, "w") as f:
            f.write(creds.to_json())


def _is_server_env() -> bool:
    """Retourne True si on tourne sur un serveur (Railway, etc.)."""
    return bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))
