# =============================================================================
# language_detector.py — Détection FR / EN
# =============================================================================

from langdetect import detect, LangDetectException

# Sujets fixes émis par Centris et Realtor.ca selon la langue
_SUBJECT_FR = [
    "demande d'information",
    "demande générale",
    "demande de visite",
    "nepasrepondre",
]
_SUBJECT_EN = [
    "information request",
    "general inquiry",
    "visit request",
    "do-not-reply",
]


def detect_language(text: str, subject: str = "") -> str:
    """
    Détecte la langue en deux étapes :
    1. Sujet — mots-clés fixes Centris/Realtor (100 % fiable)
    2. Corps  — langdetect (fallback)
    Par défaut : 'fr'.
    """
    if subject:
        lang = _detect_from_subject(subject)
        if lang:
            return lang

    return _detect_from_body(text)


def _detect_from_subject(subject: str) -> str:
    """Retourne 'fr', 'en', ou '' si aucun pattern reconnu."""
    s = subject.lower()
    if any(kw in s for kw in _SUBJECT_FR):
        return "fr"
    if any(kw in s for kw in _SUBJECT_EN):
        return "en"
    return ""


def _detect_from_body(text: str) -> str:
    """Détection statistique via langdetect. Défaut : 'fr'."""
    if not text.strip():
        return "fr"
    try:
        return "fr" if detect(text) == "fr" else "en"
    except LangDetectException:
        return "fr"
