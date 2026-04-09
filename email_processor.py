# =============================================================================
# email_processor.py — Lecture et classification des emails entrants
# =============================================================================

import base64
import re
from typing import Optional

from bs4 import BeautifulSoup

from config import MAX_EMAILS_PER_RUN


def fetch_unread_emails(service, sender_filter: str) -> list[dict]:
    """
    Récupère les emails non lus provenant de sender_filter.
    Retourne une liste de dicts avec les champs utiles.
    """
    if isinstance(sender_filter, list):
        from_clause = " OR ".join(sender_filter)
        query = f"from:({from_clause}) is:unread"
    else:
        query = f"from:{sender_filter} is:unread"
    results = service.users().messages().list(
        userId="me", q=query, maxResults=MAX_EMAILS_PER_RUN
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="full"
        ).execute()
        parsed = _parse_email(detail)
        if parsed:
            emails.append(parsed)

    return emails


def _parse_email(msg: dict) -> Optional[dict]:
    """Extrait les champs utiles d'un message Gmail brut."""
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}

    email_id  = msg["id"]
    thread_id = msg["threadId"]
    subject   = headers.get("Subject", "(sans objet)")
    sender    = headers.get("From", "")
    reply_to  = headers.get("Reply-To", "") or headers.get("From", "")
    body      = _extract_body(msg["payload"])

    reply_address    = _extract_email_address(reply_to)
    buyer_name       = extract_buyer_name(body, reply_to)
    buyer_message    = extract_buyer_message(body)
    property_address = extract_property_address(subject, body)

    return {
        "id": email_id,
        "thread_id": thread_id,
        "subject": subject,
        "sender": sender,
        "reply_to": reply_address,
        "body": body,
        "buyer_name": buyer_name,
        "buyer_message": buyer_message,
        "property_address": property_address,
    }


def _extract_body(payload: dict) -> str:
    """
    Extrait le texte propre du payload Gmail.
    Priorité : text/plain → text/html (parsé avec BeautifulSoup).
    """
    # Cherche text/plain en priorité (récursif pour multipart)
    plain = _find_part(payload, "text/plain")
    if plain:
        return _decode_base64(plain).strip()

    # Sinon : text/html → BeautifulSoup
    html_raw = _find_part(payload, "text/html")
    if html_raw:
        return _html_to_text(_decode_base64(html_raw)).strip()

    return ""


def _find_part(payload: dict, mime_type: str) -> str:
    """Cherche récursivement un MIME type dans le payload et retourne les données base64."""
    if payload.get("mimeType") == mime_type:
        return payload.get("body", {}).get("data", "")
    for part in payload.get("parts", []):
        result = _find_part(part, mime_type)
        if result:
            return result
    return ""


def _html_to_text(html: str) -> str:
    """Convertit le HTML en texte lisible via BeautifulSoup (préserve les sauts de ligne)."""
    soup = BeautifulSoup(html, "html.parser")
    # Insérer un saut de ligne après les balises de bloc pour garder la structure
    for tag in soup.find_all(["br", "p", "div", "li", "td", "tr"]):
        tag.append("\n")
    text = soup.get_text(separator="")
    # Normaliser : supprimer les lignes vides en excès
    lines = [line.strip() for line in text.splitlines()]
    clean = "\n".join(line for line in lines if line)
    return clean


def _decode_base64(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")


def extract_buyer_name(body: str, reply_to_raw: str) -> str:
    """
    Extrait le prénom depuis le corps parsé d'un email Centris.

    Structure Centris après parsing HTML :
        Nom          ← ligne label seule
        Mohamed Mirri  ← ligne suivante = valeur
        Courriel
        ...

    Stratégie : trouver une ligne qui est exactement "Nom" ou "Name"
    puis prendre le premier mot de la ligne suivante non vide.
    """
    lines = [l.strip() for l in body.splitlines()]

    label_variants = {"nom", "name"}
    for i, line in enumerate(lines):
        if line.lower() in label_variants:
            # Cherche la prochaine ligne non vide
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j].strip()
                if next_line:
                    first_word = next_line.split()[0]
                    if len(first_word) >= 2 and "@" not in first_word and not first_word[0].isdigit():
                        return first_word.capitalize()
            break

    return ""


def extract_buyer_message(body: str) -> str:
    """
    Extrait le message rédigé par l'acheteur (section 'Message :' / 'Comments :').
    Utilisé pour la détection de langue — évite de détecter sur le texte Centris.
    Retourne le corps complet si non trouvé.
    """
    patterns = [
        r"\bMessage\s*:\s*(.+)",
        r"\bCommentaires?\s*:\s*(.+)",
        r"\bComments?\s*:\s*(.+)",
        r"\bRemarques?\s*:\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
        if match:
            msg = match.group(1).strip()
            if len(msg) >= 5:
                return msg
    return body


def extract_property_address(subject: str, body: str) -> str:
    """
    Extrait l'adresse de la propriété depuis le sujet ou le corps de l'email.
    """
    # 1. Depuis le sujet — après "pour " ou "for "
    for pattern in [r"(?:pour|for)\s+(.+?)(?:\s*[-–|]|$)", r"[-–]\s*(.+)$"]:
        match = re.search(pattern, subject, re.IGNORECASE)
        if match:
            addr = match.group(1).strip().rstrip(".")
            if len(addr) >= 5:
                return addr

    # 2. Depuis le corps
    for pattern in [
        r"(?:Adresse|Propriété|Property|Address)\s*:\s*(.+)",
        r"(?:MLS|Centris)\s*#?\s*\d+\s*[:\|–-]\s*(.+)",
    ]:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            addr = match.group(1).strip().rstrip(".")
            if len(addr) >= 5:
                return addr

    return ""


def _extract_email_address(raw: str) -> str:
    """Extrait l'adresse email d'un champ From/Reply-To."""
    match = re.search(r"<([^>]+)>", raw)
    if match:
        return match.group(1).strip()
    return raw.strip()
