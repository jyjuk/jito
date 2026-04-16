from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import AppState, JournalEntry, JournalLine, Partner, PartnerType

_CREDIT_NORMAL = {2000, 4000}


def _next_partner_id(state: AppState) -> int:
    return max((p.id for p in state.partners), default=0) + 1


def _next_entry_id(state: AppState) -> int:
    return max((e.id for e in state.entries), default=0) + 1


def _require_partner(state: AppState, partner_id: int) -> Partner:
    partner = get_partner(state, partner_id)
    if partner is None:
        raise ValueError(f"Partner {partner_id} not found")
    return partner


def add_partner(state: AppState, name: str, partner_type: PartnerType) -> Partner:
    partner = Partner(id=_next_partner_id(state), name=name, type=partner_type)
    state.partners.append(partner)
    return partner


def get_partner(state: AppState, partner_id: int) -> Partner | None:
    return next((p for p in state.partners if p.id == partner_id), None)


def _post(state: AppState, entry: JournalEntry) -> JournalEntry:
    state.entries.append(entry)
    return entry


def record_sale(
    state: AppState,
    entry_date: date,
    partner_id: int,
    amount: Decimal,
    description: str,
) -> JournalEntry:
    _require_partner(state, partner_id)
    return _post(state, JournalEntry(
        id=_next_entry_id(state),
        date=entry_date,
        description=description,
        partner_id=partner_id,
        lines=[
            JournalLine(account_code=1100, debit=amount),
            JournalLine(account_code=4000, credit=amount),
        ],
    ))


def record_customer_payment(
    state: AppState,
    entry_date: date,
    partner_id: int,
    amount: Decimal,
    description: str,
) -> JournalEntry:
    _require_partner(state, partner_id)
    return _post(state, JournalEntry(
        id=_next_entry_id(state),
        date=entry_date,
        description=description,
        partner_id=partner_id,
        lines=[
            JournalLine(account_code=1000, debit=amount),
            JournalLine(account_code=1100, credit=amount),
        ],
    ))


def record_expense(
    state: AppState,
    entry_date: date,
    partner_id: int,
    amount: Decimal,
    description: str,
) -> JournalEntry:
    _require_partner(state, partner_id)
    return _post(state, JournalEntry(
        id=_next_entry_id(state),
        date=entry_date,
        description=description,
        partner_id=partner_id,
        lines=[
            JournalLine(account_code=5000, debit=amount),
            JournalLine(account_code=2000, credit=amount),
        ],
    ))


def record_vendor_payment(
    state: AppState,
    entry_date: date,
    partner_id: int,
    amount: Decimal,
    description: str,
) -> JournalEntry:
    _require_partner(state, partner_id)
    return _post(state, JournalEntry(
        id=_next_entry_id(state),
        date=entry_date,
        description=description,
        partner_id=partner_id,
        lines=[
            JournalLine(account_code=2000, debit=amount),
            JournalLine(account_code=1000, credit=amount),
        ],
    ))


@dataclass(frozen=True)
class PnL:
    revenue: Decimal
    expenses: Decimal

    @property
    def net_income(self) -> Decimal:
        return self.revenue - self.expenses


def compute_pnl(
    state: AppState,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PnL:
    revenue = Decimal("0")
    expenses = Decimal("0")

    for entry in state.entries:
        if date_from and entry.date < date_from:
            continue
        if date_to and entry.date > date_to:
            continue
        for line in entry.lines:
            if line.account_code == 4000:
                revenue += line.credit
            elif line.account_code == 5000:
                expenses += line.debit

    return PnL(revenue=revenue, expenses=expenses)


@dataclass(frozen=True)
class PartnerLedgerLine:
    date: date
    entry_id: int
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


def compute_partner_ledger(
    state: AppState,
    partner_id: int,
) -> list[PartnerLedgerLine]:
    partner = get_partner(state, partner_id)
    if partner is None:
        return []

    is_customer = partner.type == PartnerType.CUSTOMER
    account = 1100 if is_customer else 2000

    balance = Decimal("0")
    lines: list[PartnerLedgerLine] = []

    relevant = sorted(
        (e for e in state.entries if e.partner_id == partner_id),
        key=lambda e: (e.date, e.id),
    )

    for entry in relevant:
        for jl in entry.lines:
            if jl.account_code != account:
                continue
            balance += jl.debit - jl.credit if is_customer else jl.credit - jl.debit
            lines.append(PartnerLedgerLine(
                date=entry.date,
                entry_id=entry.id,
                description=entry.description,
                debit=jl.debit,
                credit=jl.credit,
                balance=balance,
            ))

    return lines


def account_balance(state: AppState, account_code: int) -> Decimal:
    total = Decimal("0")
    for entry in state.entries:
        for line in entry.lines:
            if line.account_code != account_code:
                continue
            if account_code in _CREDIT_NORMAL:
                total += line.credit - line.debit
            else:
                total += line.debit - line.credit
    return total
