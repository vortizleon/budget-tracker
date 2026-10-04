# Budget Tracker

A simple app that automatically imports bank receipts from Gmail and helps manage personal finances. Built for Costa Rican banks (BAC, Promerica) but the email parser and categorization rules are fully customizable for others.

**macOS only.** There's no Windows support and none is planned — if you're on Windows you're on your own (WSL might work, untested).

## Stack

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logo=sqlalchemy&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)
![Gmail API](https://img.shields.io/badge/Gmail%20API-EA4335?logo=gmail&logoColor=white)
![ApexCharts](https://img.shields.io/badge/ApexCharts-FF5733?logo=chart.js&logoColor=white)

## Using the `finance-app` CLI

Once set up (see below), everything day-to-day goes through the `finance-app` command. It's installed on PATH (symlinked from `~/.local/bin/finance-app`), so it works from anywhere. Not a terminal person? Double-click `Abrir.command` (or the "Budget Tracker" shortcut the installer puts on your Desktop) to start the app and open the dashboard.

| Command | What it does |
|---|---|
| `finance-app` (or `open`) | Starts the server if it's not already running, and opens the dashboard in your browser |
| `finance-app demo` | Same, but in a Chrome window with no address bar/tabs - for presenting or screen-sharing |
| `finance-app sync [--days N]` | Pulls new transactions from Gmail. Default: last 30 days |
| `finance-app sync --start-date YYYY-MM-DD --end-date YYYY-MM-DD` | Backfills a specific date range instead (e.g. to fill a gap) - see example below |
| `finance-app recategorize [--all]` | Re-applies your categorization rules to existing transactions. Only touches `Uncategorized` ones by default; `--all` re-checks everything |
| `finance-app report [--month YYYY-MM]` | Prints a spending summary - totals, top categories, top merchants, vs. last month. Default: current month |
| `finance-app restart` | Restarts the server - use this after any backend (`.py`) code change |
| `finance-app delete-all [--yes]` | Wipes all transactions (keeps cards/accounts/categories/rules). Prompts for confirmation unless `--yes` |
| `finance-app refresh-oauth` | Forces a fresh Gmail login if the stored token stops working |
| `finance-app update` | Downloads the latest version from GitHub and copies it over this folder (same as double-clicking `Actualizar.command`). Keeps `credentials.json`, `token.json`, `*.db`, `.env` and `venv/`; backs up the database to `backups/` first |

**Examples:**

```bash
# Normal weekly sync
finance-app sync

# Backfill a specific gap (doesn't touch dates outside the range, so it
# won't re-pull everything you already have)
finance-app sync --start-date 2026-08-15 --end-date 2026-08-30

# See what you spent in a specific past month
finance-app report --month 2026-08

# Re-run your category rules against everything, e.g. after editing a rule's pattern
finance-app recategorize --all

# Start fresh (destructive - wipes all transactions, keeps config)
finance-app delete-all && finance-app sync
```

Frontend (`.html`/`.css`/`.js`) edits don't need `restart` - they're served fresh on every request - but an already-open browser tab only loads the JS once, so hard-refresh (Cmd+Shift+R) to see them.

### How often should I run this?

- **`sync`**: weekly is enough. Gmail keeps your mail indefinitely, so there's no risk of losing data by syncing infrequently - but banks occasionally change their email templates (this happened with both banks here), and a weekly sync surfaces a parsing break while it's a small, recent batch instead of months of backlog to debug at once. Sync more often (daily) if you want the dashboard to feel current.
- **`recategorize`**: only after you add or edit a rule in the Categories tab. New rules apply automatically to transactions synced *after* that point; this catches the ones synced before.
- **`report`**: once a month, a few days after the month closes, for a clean read on the month that just ended. Running it mid-month (no `--month` flag) gives you a running total of the current month instead.

A reasonable routine: `finance-app sync` weekly, `finance-app report` on the 1st-3rd of each month.

## Developer / manual setup

For working on the code itself. (If you just want to run the app, use `Instalar.command` instead — see above.)

```bash
# Install uv (https://docs.astral.sh/uv/) - no Homebrew/Xcode needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment (uv downloads Python 3.13 if you don't have it)
uv venv --python 3.13 venv

# Install packages
uv pip install --python venv/bin/python -r requirements.txt
```

**Gmail API setup:** each person who runs this app needs their own Google Cloud project with the Gmail API enabled and the OAuth client JSON downloaded to the project root (any `*.json` desktop-client file is auto-renamed to `credentials.json`) — see the "Configura tu proyecto de Google" section in [GUIA_DE_USO.md](GUIA_DE_USO.md) for the exact steps (it's in Spanish, but the Google Cloud Console click-path is the same regardless).

**Sharing with friends (they skip Google Cloud):** keep your own Google Cloud project in **Testing** status with the Gmail API enabled and a Desktop-app OAuth client. For each friend, add their Gmail under *Google Auth Platform → Audience → Test users* (max 100), then send them the client's `client_secret_*.json` **privately** (never commit it - the repo is public). They drop it in the project folder, the installer renames it, and they click through Google's "unverified app" warning once. Gmail access expires about every 7 days while the project is in Testing (they re-run *Reconnect Gmail*). Their mail and tokens stay on their own machine; you only manage the test-user list.

**When a friend asks for access (your checklist):**
1. Send them the message below. It already contains the install command.
2. When they reply with their Gmail (the one that receives the bank emails): open <https://console.cloud.google.com/auth/audience> (project selected), *Add users*, paste the exact address, *Guardar*. This step is manual - as far as I know Google has no public API for test users.
3. Send them the same `client_secret_*.json` every time (keep it in a pinned chat/note to yourself). Never post it in a public place.

Message template (Spanish):

```
Hola! Para usar Budget Tracker:
1) Abre la app Terminal (Cmd+Espacio, escribe "Terminal") y pega esto:
[ -d ~/Documents/budget-tracker ] || (mkdir -p ~/Documents && curl -fsSL https://github.com/vortizleon/budget-tracker/archive/refs/heads/main.tar.gz | tar -xz -C ~/Documents && mv ~/Documents/budget-tracker-main ~/Documents/budget-tracker); bash ~/Documents/budget-tracker/Instalar.command
2) Respóndeme con el Gmail donde recibes los correos de tu banco. Yo te agrego y te mando un archivo .json.
3) Guarda ese archivo en Documentos/budget-tracker y haz doble clic en Instalar.command otra vez.
Guía completa: https://github.com/vortizleon/budget-tracker/blob/main/GUIA_DE_USO.md
```

**What to send, and what never to send:** the client file (`client_secret_*.json`) only identifies the app - it grants no mailbox access, so it's the one file you share (privately). Never send `token.json` (it grants read access to *your* Gmail), `budgeting.db` (your transactions) or a zip of your whole project folder, which contains both. Friends get the code from the install command in the guide, not from your folder. To cut off access later, revoke the app at `myaccount.google.com/permissions` or delete/rotate the client in Google Cloud.

**Initialize the database.** Two ways to do this, both equivalent:

```bash
# Non-interactive: seeds default categories + BAC/Promerica email sources and exits.
# Cards and any other email sources then get added from the web UI (Cards tab,
# Settings tab) - this is what Instalar.command uses for non-developer installs.
venv/bin/python backend/init_db.py --seed-only

# Interactive menu: same seeding (option 1) plus cards/accounts/subscriptions
# from the terminal instead of the UI, for anyone who prefers the CLI.
venv/bin/python backend/init_db.py
```

Interactive menu:
1. Create default categories **and** seed the known-good BAC/Promerica email sources (`NotificacionBAC@baccredomatic.cr`, `alerta@baccredomatic.com`, `info@promerica.fi.cr`) — these are each bank's own sending address, the same for every customer, so new users get a working sync without having to know to add them first
2. Add a card
3. Add an account
4. Add an email source (bank notification sender) manually — for a bank other than BAC/Promerica, or a custom address; sync fetches *all* mail from each configured source and parses it; keywords are optional and unused for filtering
5. Add a subscription
6-9. List cards / accounts / email sources / subscriptions
10. Exit

**Symlink the CLI and run it** (what `Instalar.command` does for non-developers):

```bash
mkdir -p ~/.local/bin && ln -sf "$(pwd)/finance-app" ~/.local/bin/finance-app
finance-app        # open the dashboard at http://localhost:8000 - add cards there, then click "Sync Now"
finance-app sync   # equivalent from the terminal; first run triggers the Gmail OAuth flow in the browser
```

Every day-to-day CLI command also has a UI equivalent in the Settings tab (Sync Now, date-range sync, re-apply category rules, reconnect Gmail) — use whichever you prefer, they call the same backend logic.

Or run the server directly without the CLI: `venv/bin/uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000`.

---

## Tests / CI

`requirements-dev.txt` adds `pytest` and `httpx`. Run `venv/bin/python -m pytest tests` - it checks that every module imports, every page is served and the Google credentials upload/auto-detect works, all against a throwaway database. GitHub Actions (`.github/workflows/ci.yml`) repeats a clean install on Linux and macOS for every PR, and also runs `Instalar.command` on a clean Mac.

---

## Database Schema

### Cards
- Supports multiple currencies (CRC and USD)
- Stores payment due dates and cutoff dates
- Credit limits per currency

### Accounts
- IBAN support
- Balance tracking
- Multiple account types (checking, savings, cash)

### Transactions
- Links to cards via last 4 digits
- Stores original Gmail message ID (prevents duplicates)
- Auto-categorization support
- Purchase vs payment type

### Categories
- Hierarchical (parent/child relationships)
- Expense vs income types
- Auto-categorization rules

### Email Sources
- Configure multiple bank notification emails
- Fetch ALL emails from configured senders
- Parser automatically detects transaction data in email body
- Enable/disable sources without deleting them
- Sync automatically processes all active sources

---

## Customizing Email Parser

Your bank emails might have different format. To customize:

1. Run sync once and check what gets parsed
2. Open `backend/email_parser.py`
3. Adjust regex patterns in `__init__` method:
   - `amount`: How amounts are formatted
   - `currency`: Currency symbols
   - `commerce`: Merchant name patterns
   - `card_last_four`: Card number format
   - `date`: Date format

4. Test with: `venv/bin/python backend/email_parser.py`

---

## Project Structure

```
budgeting-app/
├── Instalar.command         # Double-click installer for non-developer users (macOS, installs uv + Python, no Homebrew/Xcode)
├── Actualizar.command       # Double-click updater: pulls the latest version, keeps your data
├── Abrir.command            # Double-click launcher: starts the server and opens the dashboard (no CLI needed)
├── GUIA_DE_USO.md           # Spanish-language setup + usage guide, for friends
├── finance-app               # CLI wrapper -> backend/manage.py (symlinked onto PATH)
├── backend/
│   ├── database.py          # SQLAlchemy engine/session setup
│   ├── models.py             # Card, Account, Category, Transaction, EmailSource, ...
│   ├── gmail_client.py       # Gmail API wrapper (auth + message fetch)
│   ├── email_parser.py       # Regex-based parsing of bank email bodies -> txn fields
│   ├── sync.py                # Pulls mail from active EmailSources, parses, dedupes, inserts
│   ├── crud.py / schemas.py  # DB access + Pydantic schemas for the API
│   ├── analytics.py          # Spending summaries/aggregations
│   ├── api.py                 # FastAPI app, mounts frontend, exposes REST endpoints
│   ├── manage.py              # finance-app CLI entry point (open/sync/report/etc.)
│   └── init_db.py             # Interactive setup: categories, cards, accounts, email sources
├── frontend/
│   ├── templates/index.html
│   └── static/{css,js}/      # dashboard, transactions, cards, subscriptions UI
├── credentials.json          # Gmail OAuth, per-person (you provide, gitignored)
├── token.json                # Auto-generated after first OAuth (gitignored)
├── budgeting.db               # SQLite database (auto-generated, gitignored)
├── requirements.txt
└── .gitignore
```

---

## Troubleshooting

### Gmail Authentication Issues

**Problem:** Browser doesn't open for OAuth
- Make sure `credentials.json` is in project root
- Check it's valid JSON from Google Cloud Console

**Problem:** "Access blocked: This app's request is invalid"
- Make sure you added your Gmail as a test user in OAuth consent screen
- Check Gmail API is enabled

### Parsing Issues

**Problem:** Transactions not being parsed correctly
- Run `finance-app sync` and check console output
- Look for "Could not extract amount" warnings
- Customize patterns in `email_parser.py` to match your bank format
- Test with sample HTML using the test function

### No Transactions Imported

**Problem:** Emails fetched but no transactions saved
- Check if you have cards added to database
- Verify last 4 digits match between card and emails
- Check keywords match your email subjects

---

## Notes

- Database file `budgeting.db` contains all your data - back it up!
- `token.json` contains Gmail credentials - keep it secure
- Never commit `credentials.json` or `token.json` to git (already in `.gitignore`)
