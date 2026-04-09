#!/usr/bin/env python3
# =============================================================================
# main.py — Point d'entrée du système de réponse automatique
# =============================================================================
# Usage :
#   python main.py              → traite les deux boîtes (mode réel)
#   python main.py --dry-run   → simule sans envoyer
#   python main.py --setup     → authentifie les deux comptes seulement

import argparse
import sys
from datetime import datetime

from config import ACCOUNTS
from auth import get_gmail_service
from email_processor import fetch_unread_emails
from language_detector import detect_language
from responder import send_reply, add_processed_label
from tracker import is_processed, mark_processed


def process_account(source: str, dry_run: bool = False):
    """Traite tous les nouveaux emails d'un compte (centris ou remax)."""
    account = ACCOUNTS[source]
    print(f"\n{'─'*50}")
    print(f"Compte : {account['email']}  [{source.upper()}]")
    print(f"{'─'*50}")

    try:
        service = get_gmail_service(account["token_file"], account["email"])
    except RuntimeError as e:
        print(f"  [AUTH] {e}")
        return 0

    emails  = fetch_unread_emails(service, account["sender_filter"])

    if not emails:
        print("  Aucun nouveau message.")
        return 0

    print(f"  {len(emails)} message(s) trouvé(s).")
    replied = 0

    for email in emails:
        email_id = email["id"]

        # Vérification anti-doublon
        if is_processed(email_id):
            print(f"  [SKIP] {email_id} — déjà traité.")
            continue

        lang = detect_language(email.get("buyer_message") or email["body"] or "", subject=email["subject"])
        print(f"  [→] {email['reply_to'][:40]} | langue: {lang.upper()} | objet: {email['subject'][:40]}")

        try:
            send_reply(service, source, email, lang, dry_run=dry_run)
            if not dry_run:
                add_processed_label(service, email_id)
                mark_processed(email_id)
            else:
                mark_processed(email_id)  # marquer quand même en dry-run pour éviter répétitions
            replied += 1
        except FileNotFoundError as e:
            print(f"  [ERREUR] Gabarit manquant : {e}")
        except Exception as e:
            print(f"  [ERREUR] {e}")

    return replied


def setup_auth():
    """Authentifie les deux comptes Gmail (premier lancement)."""
    print("=== Configuration OAuth2 ===")
    for source, account in ACCOUNTS.items():
        print(f"\nCompte {source.upper()} : {account['email']}")
        get_gmail_service(account["token_file"], account["email"])
        print(f"  OK — token sauvegardé dans {account['token_file']}")
    print("\nAuthentification terminée. Vous pouvez maintenant lancer : python main.py")


def main():
    parser = argparse.ArgumentParser(description="Système de réponse automatique — Phong Immobilier")
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans envoyer")
    parser.add_argument("--setup",   action="store_true", help="Configurer les deux comptes Gmail")
    parser.add_argument("--account", choices=["centris", "remax", "realtor"], help="Traiter un seul compte")
    args = parser.parse_args()

    if args.setup:
        setup_auth()
        return

    print(f"\n{'='*50}")
    print(f"  Phong Immobilier — Réponse automatique")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.dry_run:
        print(f"  MODE : DRY RUN (aucun email envoyé)")
    print(f"{'='*50}")

    sources = [args.account] if args.account else ["centris", "remax", "realtor"]
    total = 0
    for source in sources:
        total += process_account(source, dry_run=args.dry_run)

    print(f"\n  Total : {total} réponse(s) envoyée(s).")


if __name__ == "__main__":
    main()
