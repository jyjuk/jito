# Jito Ledger — Minimal Accounting App

A small double-entry accounting web app built with Python and Streamlit.

---

## Quick Start

### Docker (recommended)

```bash
docker build -t jito-ledger .
docker run -p 8501:8501 -v jito-data:/data jito-ledger
```

Open [http://localhost:8501](http://localhost:8501).

Data is persisted in a named Docker volume (`jito-data`). Omit the `-v` flag if you don't need persistence between container restarts.

### Local (without Docker)

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Data is written to `data/ledger.json` in the project directory.

### Tests

```bash
pytest tests/
```

---

## What the app does

The app models a minimal but correct accounting flow using **double-entry bookkeeping**.
Every business event produces a balanced journal entry (total debits = total credits).

### Supported flows

| Transaction | Debit | Credit |
|---|---|---|
| Sale — invoice to customer | 1100 Accounts Receivable | 4000 Revenue |
| Customer payment received | 1000 Cash | 1100 Accounts Receivable |
| Expense — bill from vendor | 5000 Expense | 2000 Accounts Payable |
| Vendor payment sent | 2000 Accounts Payable | 1000 Cash |

### Chart of accounts (fixed)

| Code | Name |
|---|---|
| 1000 | Cash |
| 1100 | Accounts Receivable |
| 2000 | Accounts Payable |
| 4000 | Revenue |
| 5000 | Expense |

### Reports

- **Profit & Loss** — Revenue vs Expenses, net income, optional date filter, account balance breakdown
- **Partner Ledger** — per-partner transaction history with running balance (customers track AR; vendors track AP)

---

## Technical decisions

### Double-entry over single-entry

Double-entry was the right choice here, not because the task required it, but because it's the only model that naturally produces a coherent balance sheet. Single-entry accounting would have made the partner ledger and P&L inconsistent with each other. The four business flows cover the full cash cycle without unnecessary complexity.

### Decimal arithmetic

All monetary values use Python's `Decimal`, not `float`. Floating-point arithmetic is unsuitable for financial calculations — `0.1 + 0.2 != 0.3` is not acceptable in an accounting context.

### JSON persistence over a database

A single JSON file is sufficient for a single-user Streamlit app. It has no runtime dependencies, is easy to inspect and debug, and keeps the deployment to a single container. Writes use a write-to-temp-then-replace pattern to avoid partial file corruption. A real production system would use a proper database with ACID guarantees.

### Pydantic for the domain model

`JournalEntry` validates that entries balance (DR = CR) at construction time. `JournalLine` validates that exactly one side is non-zero. This means invalid state is impossible to construct — the invariants are enforced by the model, not by scattered `if` checks.

### Immutable entries

Once posted, journal entries are not edited or deleted. This is how real accounting systems work — corrections are made via new entries (reversals). The app follows this principle.

### Partner ledger perspective

- **Customer balance** = cumulative `(DR - CR)` on account 1100. Positive = they owe us.
- **Vendor balance** = cumulative `(CR - DR)` on account 2000. Positive = we owe them.

This matches the natural reading of AR and AP from the company's perspective.

---

## Project structure

```
app/
  models.py       — Pydantic domain models (Partner, JournalLine, JournalEntry, AppState)
  ledger.py       — accounting logic and reporting (no I/O, pure functions)
  storage.py      — JSON persistence (load/save)
streamlit_app.py  — UI (5 pages: Journal, Record, Partners, P&L, Partner Ledger)
tests/
  test_ledger.py  — unit tests for all core logic
Dockerfile
requirements.txt
```
