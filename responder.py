# =============================================================================
# responder.py — Composition et envoi des réponses automatiques
# =============================================================================

import base64
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from bs4 import BeautifulSoup

from config import ACCOUNTS, PROCESSED_LABEL


def load_template(source: str, lang: str) -> str:
    """
    Charge le gabarit de réponse HTML.
    source : 'centris' ou 'remax'
    lang   : 'fr' ou 'en'
    Falls back to .txt if .html not found.
    """
    html_path = os.path.join("templates", f"{source}_{lang}.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    # Fallback to plain text
    txt_path = os.path.join("templates", f"{source}_{lang}.txt")
    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            return f.read()
    raise FileNotFoundError(f"Gabarit introuvable : {html_path}")


def _html_to_plain(html: str) -> str:
    """Converts HTML template to plain text using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["br", "p", "div", "li", "td", "tr"]):
        tag.append("\n")
    text = soup.get_text(separator="")
    lines = [line.strip() for line in text.splitlines()]
    clean = "\n".join(line for line in lines if line)
    return clean


def send_reply(service, source: str, email: dict, lang: str, dry_run: bool = False) -> bool:
    """
    Envoie une réponse automatique à l'adresse reply_to de l'email.

    source   : 'centris' ou 'remax'
    email    : dict retourné par email_processor
    lang     : 'fr' ou 'en'
    dry_run  : si True, affiche sans envoyer (utile pour tester)

    Retourne True si succès.
    """
    account          = ACCOUNTS[source]
    template_key     = account.get("template", source)  # permet de réutiliser un autre gabarit
    template         = load_template(template_key, lang)
    buyer_name       = email.get("buyer_name", "")
    property_address = email.get("property_address", "")

    # --- Sujet de la réponse ---
    if property_address:
        subject = (
            f"Votre demande d'information — {property_address}" if lang == "fr"
            else f"Your information request — {property_address}"
        )
    else:
        subject_prefix = "Re: " if not email["subject"].startswith("Re:") else ""
        subject = subject_prefix + email["subject"]

    # --- Substitution des placeholders dans le corps ---
    # {buyer_name} → prénom si trouvé, sinon chaîne vide (salutation par défaut)
    buyer_name_sub = f" {buyer_name}," if buyer_name else ","
    body_html = template.replace("{buyer_name}", buyer_name_sub)
    # {property_address} dans le corps (ligne Objet/Subject du gabarit)
    body_html = body_html.replace("{property_address}", property_address or email["subject"])

    # Determine if template is HTML or plain text
    is_html = body_html.lstrip().startswith("<!DOCTYPE") or body_html.lstrip().startswith("<html")

    if is_html:
        body_plain = _html_to_plain(body_html)
    else:
        body_plain = body_html
        body_html = None

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f'{account["display_name"]} <{account["email"]}>'
    msg["To"]      = email["reply_to"]
    msg["In-Reply-To"] = email["id"]
    msg["References"]  = email["id"]

    # Plain text first (fallback), HTML second (preferred by email clients)
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    if dry_run:
        print(f"\n{'='*60}")
        print(f"[DRY RUN] À           : {email['reply_to']}")
        print(f"[DRY RUN] Objet       : {subject}")
        print(f"[DRY RUN] Langue      : {lang.upper()}")
        print(f"[DRY RUN] Source      : {source.upper()}")
        print(f"[DRY RUN] Prénom      : {buyer_name or '(non trouvé)'}")
        print(f"[DRY RUN] Adresse     : {property_address or '(non trouvée)'}")
        print(f"[DRY RUN] Format      : {'HTML + plain text' if body_html else 'plain text only'}")
        print(f"[DRY RUN] Corps (plain) :\n{body_plain[:300]}...")
        print('='*60)
        return True

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    service.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": email["thread_id"]},
    ).execute()

    return True


def add_processed_label(service, email_id: str):
    """
    Ajoute le label PROCESSED_LABEL et marque l'email comme lu.
    Crée le label s'il n'existe pas.
    """
    label_id = _get_or_create_label(service, PROCESSED_LABEL)
    service.users().messages().modify(
        userId="me",
        id=email_id,
        body={
            "addLabelIds": [label_id],
            "removeLabelIds": ["UNREAD"],
        },
    ).execute()


def _get_or_create_label(service, name: str) -> str:
    """Retourne l'ID du label, le crée si nécessaire."""
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == name:
            return label["id"]

    # Créer le label
    created = service.users().labels().create(
        userId="me",
        body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    ).execute()
    return created["id"]
