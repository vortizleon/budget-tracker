"""CLI entry point for the `finance-app` wrapper script.

Subcommands:
  open (default)  Start the web server (if not already running) and open it in a browser.
  demo            Same, but in a chrome-less window (no URL bar) - for presenting/screen-sharing.
  restart         Restart the server - use this after backend (.py) code changes.
  sync            Sync transactions from all active Gmail email sources.
  recategorize    Re-apply categorization rules to existing transactions.
  report          Print a monthly spending summary (defaults to the current month).
  delete-all      Wipe all transactions (keeps cards/accounts/categories/sources).
  refresh-oauth   Force a fresh Gmail OAuth login (discards the stored token).
  update          Download the latest version from GitHub (keeps your data) - runs Actualizar.command.
"""
import argparse
import calendar
import socket
import subprocess
import sys
import time
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.database import SessionLocal, init_db
from backend.models import Transaction, Category
from backend.sync import TransactionSyncer
from backend import analytics

PORT = 8000


def port_in_use():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', PORT)) == 0


def start_server():
    print(f"Starting server on port {PORT}...")
    log_path = BASE_DIR / ".server.log"
    # backend.serve writes the (rotating) log itself, so no stdout redirect.
    subprocess.Popen(
        [str(BASE_DIR / "venv" / "bin" / "python"), "-m", "backend.serve", "127.0.0.1", str(PORT)],
        cwd=str(BASE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(30):
        if port_in_use():
            return True
        time.sleep(0.5)
    print(f"✗ Server didn't come up in time - check {log_path}")
    return False


def stop_server():
    if not port_in_use():
        print("Server isn't running.")
        return
    result = subprocess.run(["lsof", "-ti", f":{PORT}"], capture_output=True, text=True)
    pids = [p for p in result.stdout.split() if p]
    for pid in pids:
        subprocess.run(["kill", pid])
    for _ in range(20):
        if not port_in_use():
            print("✓ Server stopped.")
            return
        time.sleep(0.5)
    print("✗ Server didn't stop in time.")


def cmd_open(args):
    if not port_in_use():
        if not start_server():
            return
    else:
        print("Server already running.")

    url = f"http://localhost:{PORT}"
    print(f"Opening {url}")
    webbrowser.open(url)


def cmd_demo(args):
    """Open in Chrome's --app mode: no address bar, tabs, or toolbar - just
    the app in its own window, titled by the page's <title> instead of
    showing the URL. Good for screen-sharing/presenting."""
    if not port_in_use():
        if not start_server():
            return
    else:
        print("Server already running.")

    url = f"http://localhost:{PORT}"
    chrome_path = "/Applications/Google Chrome.app"
    if not Path(chrome_path).exists():
        print(f"✗ {chrome_path} not found - falling back to a normal browser tab.")
        webbrowser.open(url)
        return

    print(f"Opening {url} in app mode (no address bar)...")
    subprocess.Popen(
        ["open", "-na", "Google Chrome", "--args", f"--app={url}"],
        start_new_session=True,
    )


def cmd_restart(args):
    """Kill the running server (if any) and start a fresh one - needed to
    pick up backend (.py) changes. Frontend (.html/.css/.js) changes are
    served fresh on every request and only need a browser hard-refresh."""
    stop_server()
    if start_server():
        url = f"http://localhost:{PORT}"
        print(f"Opening {url}")
        webbrowser.open(url)
        print("Note: hard-refresh the browser tab (Cmd+Shift+R) to pick up frontend changes too.")


def cmd_sync(args):
    init_db()
    db = SessionLocal()
    try:
        syncer = TransactionSyncer(db)
        after_date = datetime.strptime(args.start_date, "%Y-%m-%d") if args.start_date else None
        # Gmail's "before:" is exclusive, so bump by a day to include end_date itself.
        before_date = (
            datetime.strptime(args.end_date, "%Y-%m-%d") + timedelta(days=1)
            if args.end_date else None
        )
        syncer.sync_all_active_sources(
            days_back=args.days,
            after_date=after_date,
            before_date=before_date
        )
        syncer.show_summary()
    finally:
        db.close()


def cmd_recategorize(args):
    """Re-apply CategorizationRules to existing transactions.

    New rules only affect transactions synced after they're added, so this
    sweeps previously-synced transactions - by default only the ones still
    sitting in "Uncategorized" (pass --all to re-check every transaction,
    e.g. after editing a rule's pattern).
    """
    init_db()
    db = SessionLocal()
    try:
        syncer = TransactionSyncer(db)
        query = db.query(Transaction)
        if not args.all:
            uncategorized = db.query(Category).filter(Category.name == "Uncategorized").first()
            if uncategorized:
                query = query.filter(Transaction.category_id == uncategorized.id)

        transactions = query.all()
        updated = 0
        for txn in transactions:
            category_id = syncer.match_categorization_rule(txn.commerce_name)
            if category_id and category_id != txn.category_id:
                txn.category_id = category_id
                updated += 1

        db.commit()
        print(f"✓ Checked {len(transactions)} transactions, recategorized {updated}.")
    finally:
        db.close()


def cmd_report(args):
    """Print a monthly spending summary: totals (with vs-last-month change),
    top categories, top merchants, and how many transactions still need a
    category - split by currency since CRC and USD shouldn't be added together."""
    init_db()
    db = SessionLocal()
    try:
        if args.month:
            year, month = (int(p) for p in args.month.split('-'))
        else:
            today = date.today()
            year, month = today.year, today.month

        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])

        prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
        prev_start = date(prev_year, prev_month, 1)
        prev_end = date(prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1])

        print(f"\n{'='*60}")
        print(f"Monthly Report: {start.strftime('%B %Y')}")
        print(f"{'='*60}")

        any_data = False
        for currency, symbol in (("CRC", "₡"), ("USD", "$")):
            total = db.query(func.sum(Transaction.amount)).filter(
                Transaction.date >= start, Transaction.date <= end,
                Transaction.currency == currency, Transaction.transaction_type == 'purchase'
            ).scalar() or 0
            prev_total = db.query(func.sum(Transaction.amount)).filter(
                Transaction.date >= prev_start, Transaction.date <= prev_end,
                Transaction.currency == currency, Transaction.transaction_type == 'purchase'
            ).scalar() or 0

            if not total and not prev_total:
                continue
            any_data = True

            print(f"\n{currency} spending: {symbol}{total:,.2f}")
            if prev_total:
                change = (float(total) - float(prev_total)) / float(prev_total) * 100
                arrow = '▲' if change > 0 else '▼'
                print(f"  vs {prev_start.strftime('%B')}: {symbol}{prev_total:,.2f} ({arrow} {abs(change):.1f}%)")

            categories = analytics.get_spending_by_category(db, start_date=start, end_date=end, currency=currency)
            if categories:
                print(f"  Top categories:")
                for c in categories[:5]:
                    print(f"    {c.category_name:<20} {symbol}{c.total_amount:>12,.2f}  ({c.percentage:.1f}%)")

            merchants = analytics.get_top_merchants(db, limit=5, start_date=start, end_date=end, currency=currency)
            if merchants:
                print(f"  Top merchants:")
                for m in merchants:
                    print(f"    {m.commerce_name:<30} {symbol}{m.total_amount:>12,.2f}")

        if not any_data:
            print("\nNo transactions found for this month.")

        uncategorized = db.query(Category).filter(Category.name == "Uncategorized").first()
        if uncategorized:
            count = db.query(Transaction).filter(
                Transaction.date >= start, Transaction.date <= end,
                Transaction.category_id == uncategorized.id
            ).count()
            if count:
                print(f"\n⚠ {count} transaction(s) this month still need a category.")
                print("  Add a rule in the Categories tab, or run `finance-app recategorize`.")

        print(f"\n{'='*60}\n")
    finally:
        db.close()


def cmd_delete_all(args):
    init_db()
    db = SessionLocal()
    try:
        count = db.query(Transaction).count()
        if count == 0:
            print("No transactions to delete.")
            return
        if not args.yes:
            confirm = input(f"Delete all {count} transactions? This cannot be undone. [y/N] ").strip().lower()
            if confirm != 'y':
                print("Cancelled.")
                return
        db.query(Transaction).delete()
        db.commit()
        print(f"✓ Deleted {count} transactions.")
    finally:
        db.close()


def cmd_refresh_oauth(args):
    token_path = BASE_DIR / "token.json"
    if token_path.exists():
        token_path.unlink()
        print(f"✓ Removed {token_path}")
    else:
        print("No existing token.json found.")

    # Re-authenticating opens a browser window for login.
    from backend.gmail_client import GmailClient
    GmailClient()
    print("✓ Gmail re-authenticated.")


def cmd_update(args):
    subprocess.run(["bash", str(BASE_DIR / "Actualizar.command")])


def main():
    parser = argparse.ArgumentParser(prog="finance-app")
    parser.set_defaults(func=cmd_open)
    subparsers = parser.add_subparsers(dest="command")

    open_parser = subparsers.add_parser("open", help="Start the server (if needed) and open it in a browser")
    open_parser.set_defaults(func=cmd_open)

    demo_parser = subparsers.add_parser("demo", help="Open in a chrome-less window (no URL bar) for presenting/screen-sharing")
    demo_parser.set_defaults(func=cmd_demo)

    restart_parser = subparsers.add_parser("restart", help="Restart the server to pick up backend code changes")
    restart_parser.set_defaults(func=cmd_restart)

    sync_parser = subparsers.add_parser("sync", help="Sync transactions from Gmail")
    sync_parser.add_argument("--days", type=int, default=30, help="How many days back to search (default: 30, ignored if --start-date is given)")
    sync_parser.add_argument("--start-date", type=str, help="Backfill from this date (YYYY-MM-DD) instead of --days")
    sync_parser.add_argument("--end-date", type=str, help="Backfill up to this date (YYYY-MM-DD, inclusive) - use with --start-date to fill a specific gap")
    sync_parser.set_defaults(func=cmd_sync)

    recat_parser = subparsers.add_parser("recategorize", help="Re-apply categorization rules to existing transactions")
    recat_parser.add_argument("--all", action="store_true", help="Re-check every transaction, not just Uncategorized ones")
    recat_parser.set_defaults(func=cmd_recategorize)

    report_parser = subparsers.add_parser("report", help="Print a monthly spending summary")
    report_parser.add_argument("--month", type=str, help="Month to report on, as YYYY-MM (default: current month)")
    report_parser.set_defaults(func=cmd_report)

    delete_parser = subparsers.add_parser("delete-all", help="Delete all transactions")
    delete_parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    delete_parser.set_defaults(func=cmd_delete_all)

    oauth_parser = subparsers.add_parser("refresh-oauth", help="Force a fresh Gmail OAuth login")
    oauth_parser.set_defaults(func=cmd_refresh_oauth)

    update_parser = subparsers.add_parser("update", help="Download the latest version (keeps your data)")
    update_parser.set_defaults(func=cmd_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
