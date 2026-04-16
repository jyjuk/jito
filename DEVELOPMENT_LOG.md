# Development Log

## 2026-04-16

### Domain research

Started by studying double-entry bookkeeping before writing any code. Key questions worked through:

- What is the difference between single-entry and double-entry?
- How do AR and AP relate to partner balances?
- What does a journal entry actually represent?

**Conclusion:** Double-entry is the only model that makes P&L and partner ledger consistent with each other. Single-entry would produce correct revenue/expense totals but a meaningless partner ledger.

---

### Data model design

Decided on the following structure before writing code:

- `JournalEntry` with a list of `JournalLine` objects (debit/credit per account)
- Validation at construction time: entry must balance (DR = CR), each line must have exactly one non-zero side
- `Partner` with type (customer / vendor)
- `AppState` as the root persistence object

Using `Decimal` throughout — float arithmetic produces rounding errors in financial calculations.

---

### Business flows

Four flows cover the full cash cycle:

| Flow | Debit | Credit |
|---|---|---|
| Sale | 1100 AR | 4000 Revenue |
| Customer payment | 1000 Cash | 1100 AR |
| Expense | 5000 Expense | 2000 AP |
| Vendor payment | 2000 AP | 1000 Cash |

---

### Partner ledger balance convention

Decided on the perspective of "outstanding amount from the company's point of view":

- Customer balance = cumulative `(DR - CR)` on AR 1100. Positive = they owe us.
- Vendor balance = cumulative `(CR - DR)` on AP 2000. Positive = we owe them.

---

### Bugs found during self-review

**Bug 1 — account_balance sign for credit-normal accounts**

Revenue (4000) and AP (2000) have credit normal balance. The initial implementation used `debit - credit` for all accounts, returning negative values for these two. Fixed by introducing `_CREDIT_NORMAL = {2000, 4000}` and using `credit - debit` for those accounts.

**Bug 2 — no partner validation in ledger layer**

The `record_*` functions accepted any `partner_id` without checking it exists. Business logic should not rely on UI-level guards. Fixed with `_require_partner()` helper.

---

### Storage

JSON file with atomic write (write to `.tmp`, then `replace()`). Path configurable via `DATA_FILE` env var for Docker.
