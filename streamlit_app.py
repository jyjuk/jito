from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from app import ledger as acc
from app import storage
from app.models import CHART_OF_ACCOUNTS, AppState, PartnerType

st.set_page_config(page_title="Jito Ledger", page_icon="📒", layout="wide")

_FLOWS: dict[str, tuple[str, PartnerType, str]] = {
    "Sale — Invoice to Customer":  ("sale",             PartnerType.CUSTOMER, "DR 1100 Accounts Receivable / CR 4000 Revenue"),
    "Customer Payment Received":   ("customer_payment", PartnerType.CUSTOMER, "DR 1000 Cash / CR 1100 Accounts Receivable"),
    "Expense — Bill from Vendor":  ("expense",          PartnerType.VENDOR,   "DR 5000 Expense / CR 2000 Accounts Payable"),
    "Vendor Payment Sent":         ("vendor_payment",   PartnerType.VENDOR,   "DR 2000 Accounts Payable / CR 1000 Cash"),
}


def load() -> AppState:
    return storage.load()


def save(state: AppState) -> None:
    storage.save(state)


def fmt(value: Decimal) -> str:
    return f"{value:,.2f}"


def page_journal() -> None:
    state = load()
    st.title("Journal")

    if not state.entries:
        st.info("No entries yet. Use **Record Transaction** to post the first one.")
        return

    pnl = acc.compute_pnl(state)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entries", len(state.entries))
    c2.metric("Revenue", fmt(pnl.revenue))
    c3.metric("Expenses", fmt(pnl.expenses))
    c4.metric("Net Income", fmt(pnl.net_income))

    st.divider()

    for entry in reversed(state.entries):
        partner = acc.get_partner(state, entry.partner_id) if entry.partner_id else None
        partner_tag = f" · {partner.name}" if partner else ""
        label = f"#{entry.id} · {entry.date} · {entry.description}{partner_tag}"

        with st.expander(label):
            for line in entry.lines:
                account_name = CHART_OF_ACCOUNTS[line.account_code]
                if line.debit:
                    st.markdown(f"DR &nbsp; **{line.account_code}** {account_name} &nbsp;&nbsp; `{fmt(line.debit)}`")
                else:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp; CR &nbsp; **{line.account_code}** {account_name} &nbsp;&nbsp; `{fmt(line.credit)}`")


def page_record() -> None:
    state = load()
    st.title("Record Transaction")

    tx_label = st.selectbox("Transaction type", list(_FLOWS.keys()))
    tx_type, partner_type, posting_preview = _FLOWS[tx_label]

    st.caption(f"Posting: `{posting_preview}`")
    st.divider()

    partners = [p for p in state.partners if p.type == partner_type]
    role = "Customer" if partner_type == PartnerType.CUSTOMER else "Vendor"

    if not partners:
        st.warning(f"No {role.lower()}s found. Add one in the **Partners** page first.")
        return

    col1, col2 = st.columns(2)
    with col1:
        partner_map = {p.name: p.id for p in partners}
        selected_name = st.selectbox(role, list(partner_map.keys()))
        partner_id = partner_map[selected_name]
    with col2:
        entry_date = st.date_input("Date", value=date.today())

    amount = st.number_input("Amount", min_value=0.01, step=100.0, format="%.2f", value=1000.0)
    description = st.text_input("Description", placeholder="e.g. Invoice #001 — consulting services")

    if st.button("Post Entry", type="primary"):
        if not description.strip():
            st.error("Description is required.")
            return

        handlers = {
            "sale":             acc.record_sale,
            "customer_payment": acc.record_customer_payment,
            "expense":          acc.record_expense,
            "vendor_payment":   acc.record_vendor_payment,
        }
        handlers[tx_type](state, entry_date, partner_id, Decimal(str(round(amount, 2))), description.strip())
        save(state)
        st.success("Entry posted.")
        st.rerun()


def page_partners() -> None:
    state = load()
    st.title("Partners")

    with st.form("add_partner", clear_on_submit=True):
        st.subheader("Add Partner")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name")
        with col2:
            role = st.selectbox("Type", ["customer", "vendor"])
        if st.form_submit_button("Add"):
            if not name.strip():
                st.error("Name is required.")
            else:
                acc.add_partner(state, name.strip(), PartnerType(role))
                save(state)
                st.success(f"Added: {name.strip()}")
                st.rerun()

    st.divider()

    customers = [p for p in state.partners if p.type == PartnerType.CUSTOMER]
    vendors = [p for p in state.partners if p.type == PartnerType.VENDOR]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Customers ({len(customers)})")
        for p in customers:
            st.write(f"· {p.name}")
        if not customers:
            st.caption("None yet.")
    with col2:
        st.subheader(f"Vendors ({len(vendors)})")
        for p in vendors:
            st.write(f"· {p.name}")
        if not vendors:
            st.caption("None yet.")


def page_pnl() -> None:
    state = load()
    st.title("Profit & Loss")

    use_filter = st.checkbox("Filter by date range")
    date_from = date_to = None
    if use_filter:
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("From")
        with col2:
            date_to = st.date_input("To")

    pnl = acc.compute_pnl(state, date_from, date_to)

    st.divider()

    col1, col2, col3 = st.columns(3)
    col1.metric("Revenue", fmt(pnl.revenue))
    col2.metric("Expenses", fmt(pnl.expenses))
    col3.metric("Net Income", fmt(pnl.net_income), delta=fmt(pnl.net_income), delta_color="normal")

    st.divider()

    rows = []
    for code, name in CHART_OF_ACCOUNTS.items():
        bal = acc.account_balance(state, code)
        if bal != 0:
            rows.append({"Account": f"{code} — {name}", "Balance": float(bal)})

    if rows:
        st.subheader("Account Balances")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if not state.entries:
        st.caption("No transactions recorded yet.")


def page_partner_ledger() -> None:
    state = load()
    st.title("Partner Ledger")

    if not state.partners:
        st.info("No partners yet. Add some in the **Partners** page.")
        return

    partner_map = {p.name: p.id for p in state.partners}
    selected_name = st.selectbox("Partner", list(partner_map.keys()))
    partner_id = partner_map[selected_name]
    partner = acc.get_partner(state, partner_id)

    if partner is None:
        st.error("Partner not found.")
        return
    is_customer = partner.type == PartnerType.CUSTOMER
    account_label = "1100 — Accounts Receivable" if is_customer else "2000 — Accounts Payable"
    balance_label = "Outstanding receivable (amount they owe us)" if is_customer else "Outstanding payable (amount we owe them)"
    st.caption(f"Tracking account: **{account_label}** · {balance_label}")

    lines = acc.compute_partner_ledger(state, partner_id)

    if not lines:
        st.info("No transactions for this partner yet.")
        return

    df = pd.DataFrame([
        {
            "Date":        ln.date,
            "Entry #":     ln.entry_id,
            "Description": ln.description,
            "Debit":       float(ln.debit)  if ln.debit  else None,
            "Credit":      float(ln.credit) if ln.credit else None,
            "Balance":     float(ln.balance),
        }
        for ln in lines
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    label = "Amount Owed by Customer" if is_customer else "Amount Owed to Vendor"
    st.metric(label, fmt(lines[-1].balance))


PAGES = {
    "Journal":            page_journal,
    "Record Transaction": page_record,
    "Partners":           page_partners,
    "P&L Report":         page_pnl,
    "Partner Ledger":     page_partner_ledger,
}

page = st.sidebar.radio("Navigate", list(PAGES.keys()))
st.sidebar.divider()
st.sidebar.caption("Jito Ledger · minimal accounting")

PAGES[page]()
