# =============================================================================
# responder.py — Composition et envoi des réponses automatiques
# =============================================================================

import base64
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import ACCOUNTS, PROCESSED_LABEL


def load_template(source: str, lang: str) -> str:
    """
    Charge le gabarit de réponse.
    source : 'centris' ou 'remax'
    lang   : 'fr' ou 'en'
    """
    path = os.path.join("templates", f"{source}_{lang}.txt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Gabarit introuvable : {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


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
    body_text = template.replace("{buyer_name}", f" {buyer_name}," if buyer_name else ",")
    # {property_address} dans le corps (ligne Objet/Subject du gabarit)
    body_text = body_text.replace("{property_address}", property_address or email["subject"])

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f'{account["display_name"]} <{account["email"]}>'
    msg["To"]      = email["reply_to"]
    msg["In-Reply-To"] = email["id"]
    msg["References"]  = email["id"]

    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    if dry_run:
        print(f"\n{'='*60}")
        print(f"[DRY RUN] À           : {email['reply_to']}")
        print(f"[DRY RUN] Objet       : {subject}")
        print(f"[DRY RUN] Langue      : {lang.upper()}")
        print(f"[DRY RUN] Source      : {source.upper()}")
        print(f"[DRY RUN] Prénom      : {buyer_name or '(non trouvé)'}")
        print(f"[DRY RUN] Adresse     : {property_address or '(non trouvée)'}")
        print(f"[DRY RUN] Corps :\n{body_text}")
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
