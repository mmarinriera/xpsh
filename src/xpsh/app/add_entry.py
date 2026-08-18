import streamlit as st

from xpsh import Ledger
from xpsh.ledger import Expense
from xpsh.ledger import Transfer

from . import utils


def _parse_calculator_input(expression: str) -> float:
    """Only additions and subtractions allowed"""
    expression = expression.strip().replace(" ", "").replace(",", ".")

    # Dirty trick to handle subtraction as an addition of a negative
    expression = expression.replace("-", "+-")

    num_str = expression.split("+")
    numbers = [float(n) for n in num_str]
    return sum(numbers)


def _submit_expense(ledger: Ledger) -> None:
    st.subheader("Submit an expense")

    date = st.date_input("Date of expense", value="today", format=utils.DATE_INPUT_FMT)
    col_payer, col_quantity = st.columns(2)
    with col_payer:
        payer = st.selectbox("Who payed?", options=ledger.members)
    with col_quantity:
        quantity = st.number_input("Quantity payed", min_value=0.01)
    concept = st.text_input("What was it for?", value="")

    st.markdown("How is it split?")
    assignment: dict[str, float] = {}

    cols = st.columns(len(ledger.members))
    for name, col in zip(ledger.members, cols):
        with col:
            assignment[name] = float(st.number_input(name, min_value=0, max_value=100, value=1))

    if st.button("Submit expense!"):
        if not concept:
            st.error("Enter a name for the expense.")
            return

        expense = Expense(payer=payer, quantity=quantity, concept=concept, assignment=assignment, date=date)
        ledger.add_expense(expense)
        ledger.save_to_file()
        st.success("Expense added!")


def _submit_reimbursement(ledger: Ledger) -> None:
    st.subheader("Submit a reimbursement")

    date = st.date_input("Date of reimbursement", value="today", format=utils.DATE_INPUT_FMT)
    col_recipient, col_quantity = st.columns(2)
    with col_recipient:
        recipient = st.selectbox("Who was payed?", options=ledger.members)
    with col_quantity:
        quantity = st.number_input("Quantity payed", min_value=0.01)
    concept = st.text_input("What was it?", value="Reimbursement")

    st.markdown("How is it split?")
    assignment: dict[str, float] = {}

    cols = st.columns(len(ledger.members))
    for name, col in zip(ledger.members, cols):
        with col:
            assignment[name] = float(st.number_input(name, min_value=0, max_value=100, value=1))

    if st.button("Submit reimbursement!"):
        expense = Expense(payer=recipient, quantity=-quantity, concept=concept, assignment=assignment, date=date)
        ledger.add_expense(expense)
        ledger.save_to_file()
        st.success("Reimbursement added!")


def _submit_transfer(ledger: Ledger) -> None:
    st.subheader("Submit an transfer")

    date = st.date_input("Date of expense", value="today", format=utils.DATE_INPUT_FMT)
    col_payer, col_quantity = st.columns(2)
    with col_payer:
        payer = st.selectbox("Who payed?", options=ledger.members)
    with col_quantity:
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


def _show_last_entries(ledger: Ledger, n_last_entries: int = 10) -> None:
    entries = ledger.entries[-n_last_entries:] if len(ledger.entries) > n_last_entries else ledger.entries
    member_color_map = utils.build_member_color_map(ledger.members, utils.COLOR_PALETTE)
    date = []
    payer = []
    quantity = []
    concept = []
    assignment = []
    for entry in entries[::-1]:
        date.append(entry.date.strftime(utils.DATE_FMT))
        payer.append(utils.format_member_name(entry.payer, member_color_map))
        if isinstance(entry, Expense):
            quantity.append(
                f"{entry.quantity}"
                if entry.quantity >= 0.0
                else f":color[{-entry.quantity}]{{foreground='{utils.COLOR_REIMBURSEMENT_TYPE}'}}"
            )
            concept.append(
                entry.concept
                if entry.quantity >= 0.0
                else f":color[{entry.concept}]{{foreground='{utils.COLOR_REIMBURSEMENT_TYPE}'}}"
            )
        else:
            quantity.append(f":color[{entry.quantity}]{{foreground='{utils.COLOR_TRANSFER_TYPE}'}}")
            concept.append(f":color[Transfer]{{foreground='{utils.COLOR_TRANSFER_TYPE}'}}")

        assignment.append(utils.format_assignment(entry, member_color_map))
    st.table(
        {"Date": date, "Payer": payer, "Quantity": quantity, "Concept": concept, "Assignment/Recipient": assignment}
    )


def _show_balance(ledger: Ledger) -> None:
    member_color_map = utils.build_member_color_map(ledger.members, utils.COLOR_PALETTE)
    member = []
    spent = []
    paid = []
    owed = []
    for name, account in ledger.accounts.items():
        member.append(utils.format_member_name(name, member_color_map))
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
        payer.append(utils.format_member_name(transfer.payer, member_color_map))
        recipient.append(utils.format_member_name(transfer.recipient, member_color_map))
        quantity.append(f"{transfer.quantity:.2f}")
    st.subheader("Transfers to settle")
    st.table({"From": payer, "To": recipient, "Quantity": quantity})


ENTRY_TYPES = ("Expense", "Reimbursment", "Transfer")


def add_entry(ledger: Ledger) -> None:

    with st.expander("Calculator (only addition and subtraction allowed)", expanded=False):
        calculator_input = st.text_input("Type add operation.", value="")
        if calculator_input:
            try:
                result = _parse_calculator_input(calculator_input)
                st.success(f"Result = {result:.2f}")
            except ValueError:
                st.error("Invalid input")

    entry_type = st.radio("Type of entry", options=ENTRY_TYPES, horizontal=True)

    if entry_type == ENTRY_TYPES[0]:
        _submit_expense(ledger)
    elif entry_type == ENTRY_TYPES[1]:
        _submit_reimbursement(ledger)
    else:
        _submit_transfer(ledger)

    with st.expander("Balance", expanded=True):
        _show_balance(ledger)

    with st.expander("Last entries"):
        _show_last_entries(ledger)
