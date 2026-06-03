import sys
from pathlib import Path

import streamlit as st

from xpsh import Expense
from xpsh import Ledger
from xpsh import LedgerEntry
from xpsh import Transfer
from xpsh import get_version
from xpsh.scripts import utils

DATE_FMT = "%d/%m/%Y"
DATE_INPUT_FMT = "DD/MM/YYYY"
COLOR_PALETTE = [
    "#0077ff",
    "#a75efc",
    "#ffee00",
    "#fa6d1b",
    "#178552",
    "#c20078",
    "#fff78b",
    "#f5a7ff",
    "#2cffa7",
]
COLOR_TRANSFER_TYPE = "#26f0ff"


def _parse_calculator_input(expression: str) -> float:
    """Only additions and subtractions allowed"""
    expression = expression.strip().replace(" ", "").replace(",", ".")

    # Dirty trick to handle subtraction as an addition of a negative
    expression = expression.replace("-", "+-")

    num_str = expression.split("+")
    st.text(num_str)
    numbers = [float(n) for n in num_str]
    return sum(numbers)


def _submit_expense(ledger: Ledger) -> None:
    st.subheader("Submit an expense")

    date = st.date_input("Date of expense", value="today", format=DATE_INPUT_FMT)
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

    date = st.date_input("Date of expense", value="today", format=DATE_INPUT_FMT)
    payer = st.selectbox("Who payed?", options=ledger.members)
    quantity = st.number_input("Quantity payed", min_value=0.01)
    recipient = st.selectbox("Who received the transfer?", options=ledger.members)

    if st.button("Submit transfer!"):
        if payer == recipient:
            st.error("Select two different people to make a transfer.")
            return
        transfer = Transfer(payer=payer, quantity=quantity, recipient=recipient, date=date)
        ledger.add_transfer(transfer)
        ledger.save_to_file()
        st.success("Transfer added!")


def _format_member_name(name: str, color_map: dict[str, str]) -> str:
    color = color_map[name]
    return f":color[**{name}**]{{foreground='{color}'}}"


def _format_assignment(entry: LedgerEntry, member_color_map: dict[str, str]) -> str:
    if isinstance(entry, Transfer):
        return _format_member_name(entry.recipient, member_color_map)
    if isinstance(entry, Expense):
        assignments_str = []
        for name, fraction in entry.assignment.items():
            color = member_color_map[name]
            assignments_str.append(f":color[**{name}**={100 * fraction:.2f}%]{{foreground='{color}'}}")
        return ", ".join(assignments_str)
    raise ValueError(f"Unknown entry type: {entry}")


def _show_last_entries(ledger: Ledger, n_last_entries: int = 10) -> None:
    entries = ledger.entries[-n_last_entries:] if len(ledger.entries) > n_last_entries else ledger.entries
    member_color_map = utils.build_member_color_map(ledger.members, COLOR_PALETTE)
    date = []
    payer = []
    quantity = []
    concept = []
    assignment = []
    for entry in entries[::-1]:
        date.append(entry.date.strftime(DATE_FMT))
        payer.append(_format_member_name(entry.payer, member_color_map))
        quantity.append(f"{entry.quantity}")
        concept.append(
            entry.concept if isinstance(entry, Expense) else f":color[Transfer]{{foreground='{COLOR_TRANSFER_TYPE}'}}"
        )
        assignment.append(_format_assignment(entry, member_color_map))
    st.table(
        {"Date": date, "Payer": payer, "Quantity": quantity, "Concept": concept, "Assignment/Recipient": assignment}
    )


def _show_balance(ledger: Ledger) -> None:
    member_color_map = utils.build_member_color_map(ledger.members, COLOR_PALETTE)
    member = []
    spent = []
    paid = []
    owed = []
    for name, account in ledger.accounts.items():
        member.append(_format_member_name(name, member_color_map))
        spent.append(f"{account.spent:.2f}")
        paid.append(f"{account.paid:.2f}")
        color_owed = utils.COLOR_OWES if account.owed > 0 else utils.COLOR_IS_OWED
        owed.append(f":{color_owed}[{account.owed:.2f}]")

    st.subheader("Balance")
    st.table({"Member": member, "Total spent": spent, "Total paid": paid, "Owed": owed})
    settle_transfers = ledger.settle_transfers
    if not settle_transfers:
        st.subheader("Balance is settled!")
        return

    payer = []
    quantity = []
    recipient = []
    for transfer in settle_transfers:
        payer.append(_format_member_name(transfer.payer, member_color_map))
        recipient.append(_format_member_name(transfer.recipient, member_color_map))
        quantity.append(f"{transfer.quantity:.2f}")
    st.subheader("Transfers to settle")
    st.table({"From": payer, "To": recipient, "Quantity": quantity})


def main() -> None:
    st.title("Expense Share!")
    st.badge(f"v{get_version()}", color="violet")
    file_path = Path(sys.argv[1])

    ledger = Ledger(file_path=file_path)

    tabs = ("Expense", "Transfer")

    active_tab = st.pills(
        "Type of entry",
        tabs,
        key="active_tab",
        default="Expense",
    )

    with st.expander("Calculator (only addition and subtraction allowed)", expanded=False):
        calculator_input = st.text_input("Type add operation.", value="")
        if calculator_input:
            try:
                result = _parse_calculator_input(calculator_input)
                st.success(f"Result = {result:.2f}")
            except ValueError:
                st.error("Invalid input")

    if active_tab == tabs[0]:
        _submit_expense(ledger)
    else:
        _submit_transfer(ledger)

    with st.expander("Last entries"):
        _show_last_entries(ledger)

    with st.expander("Balance"):
        _show_balance(ledger)


if __name__ == "__main__":
    main()
