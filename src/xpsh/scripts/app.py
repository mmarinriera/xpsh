import datetime
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from xpsh.ledger import Expense
from xpsh.ledger import Ledger
from xpsh.ledger import Transfer


def _submit_expense(ledger: Ledger) -> None:
    st.subheader("Submit an expense")

    date = datetime.date.today()
    payer = st.selectbox("Who payed?", options=ledger.members)
    quantity = st.number_input("Quantity payed", min_value=0.01)
    concept = st.text_input("What was it for?", value="")

    st.markdown("How is it split?")
    assignment = {}

    cols = st.columns(len(ledger.members))
    for name, col in zip(ledger.members, cols):
        with col:
            assignment[name] = st.number_input(name, min_value=0, max_value=100, value=1)

    if st.button("Submit expense!"):
        if not concept:
            st.error("Enter a name for the expense.")
            return

        expense = Expense(payer=payer, quantity=quantity, concept=concept, assignment=assignment, date=date)
        ledger.add_expense(expense)
        ledger.save_to_file()
        st.success("Expense added!")


def _submit_transfer(ledger: Ledger) -> None:
    st.subheader("Submit an transfer")

    payer = st.selectbox("Who payed?", options=ledger.members)
    quantity = st.number_input("Quantity payed", min_value=0.01)
    recipient = st.selectbox("Who received the transfer?", options=ledger.members)
    date = datetime.date.today()

    if st.button("Submit transfer!"):
        if payer == recipient:
            st.error("Select two different people to make a transfer.")
            return
        transfer = Transfer(payer=payer, quantity=quantity, recipient=recipient, date=date)
        ledger.add_transfer(transfer)
        ledger.save_to_file()
        st.success("Transfer added!")


def _show_last_entries(ledger: Ledger, n_last_entries: int = 10) -> None:
    entries = ledger.entries[:-n_last_entries] if len(ledger.entries) > n_last_entries else ledger.entries
    records = []
    for entry in entries:
        output = entry.to_output().split(",")
        date = output.pop(0)
        payer = output.pop(0)
        quantity = output.pop(0)
        concept = output.pop(0) if isinstance(entry, Expense) else "Transfer"
        assignment = ", ".join(output) if isinstance(entry, Expense) else output[0]
        records.append((date, payer, quantity, concept, assignment))
    columns = ["Date", "Payer", "Quantity", "Concept", "Assignment/Recipient"]
    table = pd.DataFrame.from_records(records[::-1], columns=columns)
    st.table(table)


def _show_balance(ledger: Ledger) -> None:
    records = []
    for name, account in ledger.accounts.items():
        records.append((name, f"{account.spent:.2f}", f"{account.paid:.2f}", f"{account.owed:.2f}"))

    columns = ["Member", "Total spent", "Total paid", "Owed"]
    table = pd.DataFrame.from_records(records, columns=columns)
    st.subheader("Balance")
    st.table(table)
    settle_transfers = ledger.settle_transfers
    if not settle_transfers:
        return
    records_settle = []
    for transfer in settle_transfers:
        records_settle.append((transfer.payer, transfer.recipient, f"{transfer.quantity:.2f}"))
    columns_settle = ["From", "To", "Quantity"]
    table_settle = pd.DataFrame.from_records(records_settle, columns=columns_settle)
    st.subheader("Transfers to settle")
    st.table(table_settle)


def main() -> None:
    st.title("Expense Share!")
    file_path = Path(sys.argv[1])

    ledger = Ledger(file_path=file_path)

    active_tab = st.pills(
        "Type of entry",
        ("Expense", "Transfer"),
        key="active_tab",
        label_visibility="collapsed",
        default="Expense",
    )

    if active_tab == "Expense":
        _submit_expense(ledger)
    else:
        _submit_transfer(ledger)

    with st.expander("Last entries"):
        _show_last_entries(ledger)

    with st.expander("Balance"):
        _show_balance(ledger)


if __name__ == "__main__":
    main()
