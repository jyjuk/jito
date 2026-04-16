from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app import ledger as acc
from app.models import AppState, JournalEntry, JournalLine, PartnerType


@pytest.fixture
def state() -> AppState:
    return AppState()


@pytest.fixture
def customer(state: AppState):
    return acc.add_partner(state, "Acme Corp", PartnerType.CUSTOMER)


@pytest.fixture
def vendor(state: AppState):
    return acc.add_partner(state, "Office Supplies Ltd", PartnerType.VENDOR)


def test_journal_entry_must_balance() -> None:
    with pytest.raises(ValueError, match="balance"):
        JournalEntry(
            id=1,
            date=date.today(),
            description="Unbalanced entry",
            lines=[
                JournalLine(account_code=1000, debit=Decimal("100")),
                JournalLine(account_code=4000, credit=Decimal("90")),
            ],
        )


def test_journal_line_rejects_unknown_account() -> None:
    with pytest.raises(ValueError, match="Unknown account"):
        JournalLine(account_code=9999, debit=Decimal("100"))


def test_journal_line_rejects_both_sides_zero() -> None:
    with pytest.raises(ValueError):
        JournalLine(account_code=1000, debit=Decimal("0"), credit=Decimal("0"))


def test_journal_line_rejects_both_sides_nonzero() -> None:
    with pytest.raises(ValueError):
        JournalLine(account_code=1000, debit=Decimal("100"), credit=Decimal("50"))


def test_record_sale_posts_to_ar_and_revenue(state: AppState, customer) -> None:
    entry = acc.record_sale(state, date(2024, 1, 10), customer.id, Decimal("1000"), "Invoice #001")
    ar = next(l for l in entry.lines if l.account_code == 1100)
    rev = next(l for l in entry.lines if l.account_code == 4000)
    assert ar.debit == Decimal("1000")
    assert rev.credit == Decimal("1000")


def test_record_sale_appended_to_state(state: AppState, customer) -> None:
    acc.record_sale(state, date(2024, 1, 10), customer.id, Decimal("500"), "Invoice #002")
    assert len(state.entries) == 1


def test_customer_payment_posts_to_cash_and_ar(state: AppState, customer) -> None:
    entry = acc.record_customer_payment(state, date(2024, 1, 15), customer.id, Decimal("600"), "Payment received")
    cash = next(l for l in entry.lines if l.account_code == 1000)
    ar = next(l for l in entry.lines if l.account_code == 1100)
    assert cash.debit == Decimal("600")
    assert ar.credit == Decimal("600")


def test_record_expense_posts_to_expense_and_ap(state: AppState, vendor) -> None:
    entry = acc.record_expense(state, date(2024, 1, 5), vendor.id, Decimal("800"), "Office supplies")
    exp = next(l for l in entry.lines if l.account_code == 5000)
    ap = next(l for l in entry.lines if l.account_code == 2000)
    assert exp.debit == Decimal("800")
    assert ap.credit == Decimal("800")


def test_vendor_payment_posts_to_ap_and_cash(state: AppState, vendor) -> None:
    entry = acc.record_vendor_payment(state, date(2024, 1, 20), vendor.id, Decimal("800"), "Pay supplier")
    ap = next(l for l in entry.lines if l.account_code == 2000)
    cash = next(l for l in entry.lines if l.account_code == 1000)
    assert ap.debit == Decimal("800")
    assert cash.credit == Decimal("800")


def test_entry_ids_are_sequential(state: AppState, customer) -> None:
    e1 = acc.record_sale(state, date(2024, 1, 1), customer.id, Decimal("100"), "First")
    e2 = acc.record_sale(state, date(2024, 1, 2), customer.id, Decimal("200"), "Second")
    assert e2.id == e1.id + 1


def test_partner_ids_are_sequential(state: AppState) -> None:
    p1 = acc.add_partner(state, "Customer A", PartnerType.CUSTOMER)
    p2 = acc.add_partner(state, "Vendor B", PartnerType.VENDOR)
    assert p2.id == p1.id + 1


def test_pnl_sums_revenue_and_expenses(state: AppState, customer, vendor) -> None:
    acc.record_sale(state, date(2024, 1, 1), customer.id, Decimal("5000"), "Sale")
    acc.record_expense(state, date(2024, 1, 5), vendor.id, Decimal("2000"), "Rent")
    pnl = acc.compute_pnl(state)
    assert pnl.revenue == Decimal("5000")
    assert pnl.expenses == Decimal("2000")
    assert pnl.net_income == Decimal("3000")


def test_pnl_date_filter_from(state: AppState, customer) -> None:
    acc.record_sale(state, date(2024, 1, 1), customer.id, Decimal("5000"), "Jan sale")
    acc.record_sale(state, date(2024, 2, 1), customer.id, Decimal("3000"), "Feb sale")
    pnl = acc.compute_pnl(state, date_from=date(2024, 2, 1))
    assert pnl.revenue == Decimal("3000")


def test_pnl_date_filter_to(state: AppState, customer) -> None:
    acc.record_sale(state, date(2024, 1, 1), customer.id, Decimal("5000"), "Jan sale")
    acc.record_sale(state, date(2024, 2, 1), customer.id, Decimal("3000"), "Feb sale")
    pnl = acc.compute_pnl(state, date_to=date(2024, 1, 31))
    assert pnl.revenue == Decimal("5000")


def test_pnl_empty_state(state: AppState) -> None:
    pnl = acc.compute_pnl(state)
    assert pnl.revenue == Decimal("0")
    assert pnl.net_income == Decimal("0")


def test_customer_ledger_invoice_then_partial_payment(state: AppState, customer) -> None:
    acc.record_sale(state, date(2024, 1, 1), customer.id, Decimal("1000"), "Invoice")
    acc.record_customer_payment(state, date(2024, 1, 10), customer.id, Decimal("600"), "Partial payment")
    lines = acc.compute_partner_ledger(state, customer.id)
    assert len(lines) == 2
    assert lines[0].balance == Decimal("1000")
    assert lines[1].balance == Decimal("400")


def test_customer_ledger_full_payment_settles_to_zero(state: AppState, customer) -> None:
    acc.record_sale(state, date(2024, 1, 1), customer.id, Decimal("500"), "Invoice")
    acc.record_customer_payment(state, date(2024, 1, 5), customer.id, Decimal("500"), "Full payment")
    lines = acc.compute_partner_ledger(state, customer.id)
    assert lines[-1].balance == Decimal("0")


def test_vendor_ledger_bill_then_payment(state: AppState, vendor) -> None:
    acc.record_expense(state, date(2024, 1, 1), vendor.id, Decimal("800"), "Bill")
    acc.record_vendor_payment(state, date(2024, 1, 15), vendor.id, Decimal("800"), "Paid")
    lines = acc.compute_partner_ledger(state, vendor.id)
    assert len(lines) == 2
    assert lines[0].balance == Decimal("800")
    assert lines[1].balance == Decimal("0")


def test_partner_ledger_unknown_partner_returns_empty(state: AppState) -> None:
    assert acc.compute_partner_ledger(state, partner_id=999) == []


def test_record_sale_rejects_unknown_partner(state: AppState) -> None:
    with pytest.raises(ValueError, match="not found"):
        acc.record_sale(state, date(2024, 1, 1), 999, Decimal("100"), "Invoice")


def test_account_balance_cash(state: AppState, customer, vendor) -> None:
    acc.record_sale(state, date(2024, 1, 1), customer.id, Decimal("1000"), "Invoice")
    acc.record_customer_payment(state, date(2024, 1, 5), customer.id, Decimal("1000"), "Payment")
    acc.record_expense(state, date(2024, 1, 2), vendor.id, Decimal("300"), "Supplies")
    acc.record_vendor_payment(state, date(2024, 1, 6), vendor.id, Decimal("300"), "Paid")
    assert acc.account_balance(state, 1000) == Decimal("700")


def test_account_balance_credit_normal_accounts(state: AppState, customer, vendor) -> None:
    acc.record_sale(state, date(2024, 1, 1), customer.id, Decimal("300"), "Invoice")
    acc.record_expense(state, date(2024, 1, 2), vendor.id, Decimal("120"), "Supplies")
    assert acc.account_balance(state, 4000) == Decimal("300")
    assert acc.account_balance(state, 2000) == Decimal("120")
