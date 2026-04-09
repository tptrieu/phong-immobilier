# =============================================================================
# tracker.py — Suivi des emails déjà traités (évite les réponses doubles)
# =============================================================================

import json
import os
from datetime import datetime

from config import PROCESSED_FILE


def load_processed() -> set:
    """Charge les IDs des emails déjà traités."""
    if not os.path.exists(PROCESSED_FILE):
        return set()
    with open(PROCESSED_FILE, "r") as f:
        data = json.load(f)
    return set(data.get("ids", []))


def mark_processed(email_id: str):
    """Ajoute un email_id à la liste des traités."""
    processed = load_processed()
    processed.add(email_id)
    _save(processed)


def is_processed(email_id: str) -> bool:
    return email_id in load_processed()


def _save(ids: set):
    with open(PROCESSED_FILE, "w") as f:
        json.dump({
            "ids": list(ids),
            "last_updated": datetime.now().isoformat(),
        }, f, indent=2)
