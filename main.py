#!/usr/bin/env python3
# =============================================================================
# main.py — Système de réponse automatique Phong Immobilier
# =============================================================================
# Usage :
#   python main.py            → scheduler interne (Railway / serveur)
#   python main.py --once     → exécution unique et exit (test, cron externe)
#   python main.py --dry-run  → exécution unique sans envoyer
#   python main.py --setup    → authentification OAuth2 interactive (local)

import argparse
import time
import schedule
from datetime import datetime

from config import ACCOUNTS
from auth import get_gmail_service
from email_processor import fetch_unread_emails
from language_detector import detect_language
from responder import send_reply, add_processed_label
from tracker import is_processed, mark_processed
from followup import add_pending_lead, check_and_send_followups


# -----------------------------------------------------------------------------
# Traitement d'un compte
# -----------------------------------------------------------------------------

def process_account(source: str, dry_run: bool = False):
    """
    Traite un compte Gmail et retourne (replied_count, service_or_None).
    """
    account = ACCOUNTS[source]
    print(f"\n{'─'*50}")
    print(f"Compte : {account['email']}  [{source.upper()}]")
    print(f"{'─'*50}")

    try:
        service = get_gmail_service(account["token_file"], account["email"])
    except RuntimeError as e:
        print(f"  [AUTH] {e}")
        return 0, None

    emails = fetch_unread_emails(service, account["sender_filter"])

    if not emails:
        print("  Aucun nouveau message.")
        return 0, service

    print(f"  {len(emails)} message(s) trouvé(s).")
    replied = 0

    for email in emails:
        email_id = email["id"]

        if is_processed(email_id):
            print(f"  [SKIP] {email_id} — déjà traité.")
            continue

        lang = detect_language(
            email.get("buyer_message") or email["body"] or "",
            subject=email["subject"],
            sender=email["sender"],
        )
        print(f"  [→] {email['reply_to'][:40]} | langue: {lang.upper()} | objet: {email['subject'][:40]}")

        try:
            send_reply(service, source, email, lang, dry_run=dry_run)
            if not dry_run:
                add_processed_label(service, email_id)
                mark_processed(email_id)
                add_pending_lead(email, lang, source)
            else:
                mark_processed(email_id)
            replied += 1
        except FileNotFoundError as e:
            print(f"  [ERREUR] Gabarit manquant : {e}")
        except Exception as e:
            print(f"  [ERREUR] {e}")

    return replied, service


# -----------------------------------------------------------------------------
# Cycle complet (tous les comptes)
# -----------------------------------------------------------------------------

def run_all(dry_run: bool = False):
    print(f"\n{'='*50}")
    print(f"  Phong Immobilier — Réponse automatique")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if dry_run:
        print(f"  MODE : DRY RUN (aucun email envoyé)")
    print(f"{'='*50}")

    services = {}
    total = 0
    for source in ["centris", "remax", "realtor"]:
        replied, service = process_account(source, dry_run=dry_run)
        total += replied
        if service is not None:
            services[source] = service

    print(f"\n  Total : {total} réponse(s) envoyée(s).")

    # Vérification des relances 48h
    check_and_send_followups(services, dry_run=dry_run)


# -----------------------------------------------------------------------------
# Authentification interactive (local seulement)
# -----------------------------------------------------------------------------

def setup_auth():
    print("=== Configuration OAuth2 ===")
    for source, account in ACCOUNTS.items():
        print(f"\nCompte {source.upper()} : {account['email']}")
        get_gmail_service(account["token_file"], account["email"])
        print(f"  OK — token sauvegardé dans {account['token_file']}")
    print("\nAuthentification terminée.")


# -----------------------------------------------------------------------------
# Point d'entrée
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Réponse automatique — Phong Immobilier")
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans envoyer (exécution unique)")
    parser.add_argument("--once",    action="store_true", help="Exécuter une seule fois et quitter")
    parser.add_argument("--setup",   action="store_true", help="Configurer les comptes Gmail (local)")
    args = parser.parse_args()

    if args.setup:
        setup_auth()
        return

    if args.dry_run or args.once:
        run_all(dry_run=args.dry_run)
        return

    # --- Mode scheduler (Railway) ---
    print(f"[SCHEDULER] Démarrage — vérifications à 08:00, 13:00, 21:00")
    print(f"[SCHEDULER] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Exécuter une fois au démarrage pour traiter les emails en attente
    run_all()

    schedule.every().day.at("08:00").do(run_all)
    schedule.every().day.at("13:00").do(run_all)
    schedule.every().day.at("21:00").do(run_all)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
