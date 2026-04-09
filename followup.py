# =============================================================================
# followup.py — Suivi automatique 48h : relance si le formulaire Jotform
#               n'a pas été complété depuis l'envoi de la réponse initiale
# =============================================================================

import base64
import json
import os
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from bs4 import BeautifulSoup

from config import ACCOUNTS

FOLLOWUP_FILE = "pending_followup.json"
FOLLOWUP_DELAY_HOURS = 48


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------

def _load_leads() -> list:
    """Charge les leads en attente depuis pending_followup.json."""
    if not os.path.exists(FOLLOWUP_FILE):
        return []
    with open(FOLLOWUP_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("leads", [])


def _save_leads(leads: list):
    """Sauvegarde les leads dans pending_followup.json."""
    with open(FOLLOWUP_FILE, "w", encoding="utf-8") as f:
        json.dump({"leads": leads}, f, indent=2, ensure_ascii=False)


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def add_pending_lead(email_dict: dict, lang: str, source: str):
    """
    Ajoute un lead à pending_followup.json après l'envoi d'une réponse initiale.
    Évite les doublons par email id.
    """
    leads = _load_leads()
    lead_id = email_dict.get("id", "")

    # Vérifier les doublons
    for lead in leads:
        if lead.get("id") == lead_id:
            return  # Déjà présent

    new_lead = {
        "id": lead_id,
        "buyer_email": email_dict.get("reply_to", ""),
        "buyer_name": email_dict.get("buyer_name", ""),
        "lang": lang,
        "source": source,
        "property_address": email_dict.get("property_address", ""),
        "sent_at": datetime.now().isoformat(),
        "followup_sent": False,
    }
    leads.append(new_lead)
    _save_leads(leads)
    print(f"  [FOLLOWUP] Lead ajouté : {new_lead['buyer_email']} ({lang.upper()})")


def check_and_send_followups(services_dict: dict, dry_run: bool = False):
    """
    Parcourt les leads en attente et envoie un rappel si :
    - 48h se sont écoulées depuis l'envoi initial
    - Aucune réponse Jotform détectée dans la boîte Gmail

    services_dict : {source: gmail_service}
    """
    leads = _load_leads()
    if not leads:
        print("\n  [FOLLOWUP] Aucun lead en attente.")
        return

    print(f"\n  [FOLLOWUP] Vérification de {len(leads)} lead(s) en attente...")

    now = datetime.now()
    updated_leads = []

    for lead in leads:
        if lead.get("followup_sent"):
            # Nettoyage : on retire les leads déjà suivis
            continue

        sent_at_str = lead.get("sent_at", "")
        try:
            sent_at = datetime.fromisoformat(sent_at_str)
        except (ValueError, TypeError):
            updated_leads.append(lead)
            continue

        elapsed = now - sent_at
        if elapsed < timedelta(hours=FOLLOWUP_DELAY_HOURS):
            updated_leads.append(lead)
            remaining = timedelta(hours=FOLLOWUP_DELAY_HOURS) - elapsed
            hours_left = int(remaining.total_seconds() // 3600)
            print(f"  [FOLLOWUP] {lead['buyer_email']} — encore {hours_left}h avant relance.")
            continue

        # 48h écoulées — vérifier si le formulaire a été complété
        source = lead.get("source", "")
        service = services_dict.get(source)
        if not service:
            # Essayer avec un service disponible du même compte Gmail
            account_email = ACCOUNTS.get(source, {}).get("email", "")
            for s, svc in services_dict.items():
                if ACCOUNTS.get(s, {}).get("email") == account_email:
                    service = svc
                    break

        if not service:
            print(f"  [FOLLOWUP] Pas de service Gmail disponible pour source={source}, skip.")
            updated_leads.append(lead)
            continue

        buyer_email = lead.get("buyer_email", "")
        if _has_form_response(service, buyer_email, sent_at_str):
            print(f"  [FOLLOWUP] {buyer_email} — formulaire reçu, pas de relance.")
            # Lead complété : ne pas conserver
            continue

        # Envoyer la relance
        print(f"  [FOLLOWUP] {buyer_email} — 48h sans formulaire, envoi relance ({lead['lang'].upper()})...")
        try:
            _send_followup(service, lead, dry_run=dry_run)
            lead["followup_sent"] = True
            # Ne pas conserver les leads suivis (nettoyage au prochain passage)
        except Exception as e:
            print(f"  [FOLLOWUP] Erreur envoi relance pour {buyer_email}: {e}")
            updated_leads.append(lead)

    _save_leads(updated_leads)


# -----------------------------------------------------------------------------
# Helpers privés
# -----------------------------------------------------------------------------

def _has_form_response(service, buyer_email: str, after_date_str: str) -> bool:
    """
    Vérifie si un email contenant l'adresse de l'acheteur est arrivé
    APRÈS la date d'envoi de la réponse initiale (signe que Jotform a notifié).

    Query Gmail: in:inbox "{buyer_email}" after:YYYY/MM/DD
    """
    try:
        sent_at = datetime.fromisoformat(after_date_str)
        date_str = sent_at.strftime("%Y/%m/%d")
    except (ValueError, TypeError):
        return False

    query = f'in:inbox "{buyer_email}" after:{date_str}'
    try:
        results = service.users().messages().list(
            userId="me", q=query, maxResults=1
        ).execute()
        messages = results.get("messages", [])
        return len(messages) > 0
    except Exception as e:
        print(f"  [FOLLOWUP] Erreur Gmail search: {e}")
        return False


def _load_followup_template(lang: str) -> str:
    """Charge le gabarit HTML de relance."""
    path = os.path.join("templates", f"followup_{lang}.html")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Gabarit de relance introuvable : {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _html_to_plain(html: str) -> str:
    """Convertit HTML en texte via BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["br", "p", "div", "li", "td", "tr"]):
        tag.append("\n")
    text = soup.get_text(separator="")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _send_followup(service, lead: dict, dry_run: bool = False):
    """Compose et envoie l'email de relance."""
    lang = lead.get("lang", "fr")
    source = lead.get("source", "centris")
    buyer_email = lead.get("buyer_email", "")
    buyer_name = lead.get("buyer_name", "")
    property_address = lead.get("property_address", "")

    account = ACCOUNTS.get(source, ACCOUNTS.get("centris"))

    html_template = _load_followup_template(lang)
    buyer_name_sub = f" {buyer_name}," if buyer_name else ","
    body_html = html_template.replace("{buyer_name}", buyer_name_sub)
    body_plain = _html_to_plain(body_html)

    if lang == "fr":
        subject = (
            f"Suivi — {property_address}" if property_address
            else "Suivi de votre demande d'information"
        )
    else:
        subject = (
            f"Follow-up — {property_address}" if property_address
            else "Follow-up on your information request"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f'{account["display_name"]} <{account["email"]}>'
    msg["To"] = buyer_email

    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    if dry_run:
        print(f"\n{'='*60}")
        print(f"[DRY RUN FOLLOWUP] À      : {buyer_email}")
        print(f"[DRY RUN FOLLOWUP] Objet  : {subject}")
        print(f"[DRY RUN FOLLOWUP] Langue : {lang.upper()}")
        print(f"[DRY RUN FOLLOWUP] Prénom : {buyer_name or '(non trouvé)'}")
        print('='*60)
        return

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()
    print(f"  [FOLLOWUP] Relance envoyée à {buyer_email}")
