# Budget Tracker

A simple app that automatically imports bank receipts from Gmail and helps manage personal finances. Built for Costa Rican banks (BAC, Promerica) but the email parser and categorization rules are fully customizable for others.

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

Once set up (see below), everything day-to-day goes through the `finance-app` command. It's installed on PATH (symlinked to `./finance-app` in this directory), so it works from anywhere.

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

## Milestone 1: Gmail Ingestion + Database ✅

### What We Built

- ✅ Gmail API integration with OAuth authentication
- ✅ Email fetching and parsing
- ✅ SQLite database with multi-currency card support
- ✅ Configurable email sources (multiple banks)
- ✅ CLI sync tool
- ✅ Database management tools

---

## Setup Instructions

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On Mac/Linux
# or
venv\Scripts\activate  # On Windows

# Install packages
pip install -r requirements.txt
```

### 2. Gmail API Setup

You should have already:
- Created a Google Cloud project
- Enabled Gmail API
- Downloaded `credentials.json` to project root

If not, see the Gmail API setup section in the mentor instructions.

### 3. Initialize Database & Configure

```bash
python backend/init_db.py
```

This interactive tool lets you:
- Create the SQLite database (`budgeting.db`)
- Create default categories
- Add your cards and accounts
- **Configure email sources** (bank notification emails)

**Important Setup Steps:**
1. Choose option `1` → Create default categories
2. Choose option `2` → Add your cards (with correct last 4 digits!)
3. Choose option `4` → Add email source:
   - Example: `notificacion@notificacionesbaccr.com`
   - Keywords: Optional (not used for filtering - all emails fetched and parsed)

---

## Usage

### Sync Transactions from Gmail

```bash
python backend/sync.py
```

The sync script will:
1. Load all configured email sources from database
2. Ask how many days back to search (default: 30)
3. Sync from **all active email sources** automatically

**First time running:**
- Browser will open for Gmail OAuth authentication
- Grant "Read Gmail" permission
- Token saved to `token.json` for future use

**What happens:**
- Fetches emails from all configured sources
- Parses transaction details (amount, date, commerce, card)
- Saves to database (skipping duplicates)
- Shows summary per source and overall totals

**Note:** Make sure you've added at least one email source via `init_db.py` first!

### Run the Web UI

Start the FastAPI server to access the web interface:

```bash
# Activate virtual environment first
source venv/bin/activate  # On Mac/Linux
# or
venv\Scripts\activate  # On Windows

# Start the API server
uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

Then open your browser to:
- **Web UI:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs (interactive Swagger UI)
- **Alternative API Docs:** http://localhost:8000/redoc

The web UI provides:
- Dashboard with spending overview
- Transaction management and categorization
- Card and account management
- Subscription tracking
- Balance summaries (manual vs. available)

**Note:** The server runs with `--reload` flag, so it will automatically restart when you make code changes.

### Test Individual Components

**Test Gmail connection:**
```bash
python backend/gmail_client.py
```

**Test email parser:**
```bash
python backend/email_parser.py
```

### Manage Database

```bash
python backend/init_db.py
```

Interactive menu options:
1. Create default categories
2. Add a card
3. Add an account
4. **Add an email source** (configure bank notification emails)
5. List cards
6. List accounts
7. **List email sources**
8. Exit

**Managing Email Sources:**
- Add multiple banks (e.g., BAC, BCR, Promerica)
- Just provide the sender email address
- Sync fetches ALL emails from each source and parses them for transaction data
- No subject filtering - parser intelligently extracts transaction info

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

4. Test with: `python backend/email_parser.py`

---

## Project Structure

```
budgeting-app/
├── backend/
│   ├── __init__.py
│   ├── database.py          # SQLAlchemy setup
│   ├── models.py            # Database models
│   ├── gmail_client.py      # Gmail API wrapper
│   ├── email_parser.py      # Email parsing logic
│   ├── sync.py              # Main sync script
│   └── init_db.py           # Database setup tool
├── credentials.json         # Gmail OAuth (you provide)
├── token.json              # Auto-generated after first OAuth
├── budgeting.db            # SQLite database (auto-generated)
├── requirements.txt
├── .gitignore
└── README.md
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
- Run `python backend/sync.py` and check console output
- Look for "Could not extract amount" warnings
- Customize patterns in `email_parser.py` to match your bank format
- Test with sample HTML using the test function

### No Transactions Imported

**Problem:** Emails fetched but no transactions saved
- Check if you have cards added to database
- Verify last 4 digits match between card and emails
- Check keywords match your email subjects

---

## Next Steps (Milestone 2)

Coming next:
- FastAPI backend with REST endpoints
- Web UI to view/edit transactions
- Category assignment interface
- Card and account management

---

## Notes

- Database file `budgeting.db` contains all your data - back it up!
- `token.json` contains Gmail credentials - keep it secure
- Never commit `credentials.json` or `token.json` to git (already in `.gitignore`)
