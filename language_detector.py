# =============================================================================
# language_detector.py — Détection FR / EN
# =============================================================================

from langdetect import detect, LangDetectException

# Centris : l'adresse expéditeur détermine la langue à 100 %
# Observation constante depuis 2021
_SENDER_LANG = {
    "do-not-reply@centris.ca":    "en",
    "nepasrepondre@centris.ca":   "fr",
}

# Sujets fixes RE/MAX et Realtor.ca
_SUBJECT_FR = [
    "demande d'information",
    "demande générale",
    "demande de visite",
]
_SUBJECT_EN = [
    "information request",
    "general inquiry",
    "visit request",
]


def detect_language(text: str, subject: str = "", sender: str = "") -> str:
    """
    Détecte la langue selon trois étapes, par ordre de priorité :
    1. Expéditeur Centris (100 % fiable)
    2. Sujet RE/MAX / Realtor
    3. Corps du message via langdetect (fallback)
    """
    if sender:
        lang = _SENDER_LANG.get(sender.lower().strip())
        if lang:
            return lang

    if subject:
        lang = _detect_from_subject(subject)
        if lang:
            return lang

    return _detect_from_body(text)


def _detect_from_subject(subject: str) -> str:
    s = subject.lower()
    if any(kw in s for kw in _SUBJECT_FR):
        return "fr"
    if any(kw in s for kw in _SUBJECT_EN):
        return "en"
    return ""


def _detect_from_body(text: str) -> str:
    if not text.strip():
        return "fr"
    try:
        return "fr" if detect(text) == "fr" else "en"
    except LangDetectException:
        return "fr"
