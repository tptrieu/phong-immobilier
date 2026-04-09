# =============================================================================
# sheets.py — Journalisation des leads dans Google Sheets
# Feuille : "Leads Phong Immobilier"
# Colonnes : Date | Source | Prénom | Courriel | Téléphone | Propriété | Langue | Statut | Notes
# =============================================================================

import json
import os
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.credentials import Credentials

from config import SHEETS_ID

SHEETS_ID_FILE = "sheets_id.json"
SHEET_NAME = "Leads Phong Immobilier"
SHEET_COLUMNS = ["Date", "Source", "Prénom", "Courriel", "Téléphone", "Propriété", "Langue", "Statut", "Notes"]


def get_or_create_sheet(credentials: Credentials) -> Optional[gspread.Worksheet]:
    """
    Ouvre (ou crée) la feuille "Leads Phong Immobilier".
    L'ID du spreadsheet est lu depuis :
      1. La variable d'environnement GOOGLE_SHEETS_ID
      2. Le fichier local sheets_id.json
    Si aucun ID connu, crée un nouveau spreadsheet et sauvegarde l'ID localement.

    Retourne le Worksheet, ou None en cas d'erreur.
    """
    try:
        client = gspread.Client(auth=credentials)
        client.session = _build_requests_session(credentials)

        spreadsheet_id = _get_sheets_id()

        if spreadsheet_id:
            try:
                spreadsheet = client.open_by_key(spreadsheet_id)
            except gspread.exceptions.SpreadsheetNotFound:
                spreadsheet = _create_spreadsheet(client)
                _save_sheets_id(spreadsheet.id)
        else:
            spreadsheet = _create_spreadsheet(client)
            _save_sheets_id(spreadsheet.id)

        # Ouvrir ou créer la feuille nommée
        try:
            worksheet = spreadsheet.worksheet(SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(SHEET_COLUMNS))
            worksheet.append_row(SHEET_COLUMNS)

        return worksheet

    except Exception as e:
        print(f"  [SHEETS] Erreur get_or_create_sheet: {e}")
        return None


def log_lead(credentials: Credentials, email_dict: dict, lang: str, source: str):
    """
    Ajoute une ligne dans la feuille Google Sheets pour ce lead.
    Les erreurs sont capturées pour ne pas bloquer le flux principal.
    """
    try:
        worksheet = get_or_create_sheet(credentials)
        if worksheet is None:
            print("  [SHEETS] Impossible d'accéder à la feuille, lead non journalisé.")
            return

        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            source.upper(),
            email_dict.get("buyer_name", ""),
            email_dict.get("reply_to", ""),
            "",  # Téléphone — non extrait automatiquement
            email_dict.get("property_address", ""),
            lang.upper(),
            "Réponse envoyée",
            "",  # Notes — vide par défaut
        ]
        worksheet.append_row(row)
        print(f"  [SHEETS] Lead journalisé : {email_dict.get('reply_to', '')} ({source.upper()}/{lang.upper()})")

    except Exception as e:
        print(f"  [SHEETS] Erreur log_lead: {e}")


# -----------------------------------------------------------------------------
# Helpers privés
# -----------------------------------------------------------------------------

def _get_sheets_id() -> str:
    """Retourne l'ID du spreadsheet depuis env var ou fichier local."""
    if SHEETS_ID:
        return SHEETS_ID
    if os.path.exists(SHEETS_ID_FILE):
        try:
            with open(SHEETS_ID_FILE, "r") as f:
                data = json.load(f)
            return data.get("sheets_id", "")
        except Exception:
            return ""
    return ""


def _save_sheets_id(sheets_id: str):
    """Sauvegarde l'ID du spreadsheet localement (développement)."""
    try:
        with open(SHEETS_ID_FILE, "w") as f:
            json.dump({"sheets_id": sheets_id}, f)
        print(f"  [SHEETS] ID du spreadsheet sauvegardé dans {SHEETS_ID_FILE}: {sheets_id}")
    except Exception as e:
        print(f"  [SHEETS] Impossible de sauvegarder l'ID: {e}")


def _create_spreadsheet(client: gspread.Client) -> gspread.Spreadsheet:
    """Crée un nouveau spreadsheet avec les en-têtes."""
    spreadsheet = client.create(SHEET_NAME)
    worksheet = spreadsheet.sheet1
    worksheet.update_title(SHEET_NAME)
    worksheet.append_row(SHEET_COLUMNS)
    print(f"  [SHEETS] Nouveau spreadsheet créé : {spreadsheet.id}")
    return spreadsheet


def _build_requests_session(credentials: Credentials):
    """Construit une session requests authentifiée pour gspread."""
    import requests
    from google.auth.transport.requests import AuthorizedSession
    return AuthorizedSession(credentials)
