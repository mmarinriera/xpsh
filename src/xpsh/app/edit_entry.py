import streamlit as st

from xpsh import Expense
from xpsh import Ledger
from xpsh import LedgerEntry
from xpsh import Transfer

from . import utils


def _input_expense(expense: Expense, members: list[str]) -> Expense:
    date = st.date_input("Date of expense", value=expense.date, format=utils.DATE_INPUT_FMT)
    col_payer, col_quantity = st.columns(2)
    with col_payer:
        payer = st.selectbox("Who payed?", options=members, index=members.index(expense.payer))
    with col_quantity:
        quantity = st.number_input("Quantity payed", value=expense.quantity, min_value=0.01)
    concept = st.text_input("What was it for?", value=expense.concept)

    st.markdown("How is it split?")
    assignment: dict[str, float] = {}

    cols = st.columns(len(members))
    for name, col in zip(members, cols):
        with col:
            assignment[name] = float(
                st.number_input(name, min_value=0.0, max_value=100.0, value=expense.assignment.get(name, 0.0))
            )

    return Expense(payer=payer, quantity=quantity, concept=concept, assignment=assignment, date=date)


def _input_reimbursement(reimbursement: Expense, members: list[str]) -> Expense:
    date = st.date_input("Date of reimbursement", value=reimbursement.date, format=utils.DATE_INPUT_FMT)
    col_recipient, col_quantity = st.columns(2)
    with col_recipient:
        recipient = st.selectbox("Who was payed?", options=members, index=members.index(reimbursement.payer))
    with col_quantity:
        quantity = st.number_input("Quantity payed", value=-reimbursement.quantity, min_value=0.01)

    concept = st.text_input("What was it for?", value=reimbursement.concept)

    st.markdown("How is it split?")
    assignment: dict[str, float] = {}

    cols = st.columns(len(members))
    for name, col in zip(members, cols):
        with col:
            assignment[name] = float(
                st.number_input(name, min_value=0.0, max_value=100.0, value=reimbursement.assignment.get(name, 0.0))
            )

    return Expense(payer=recipient, quantity=-quantity, concept=concept, assignment=assignment, date=date)


def _input_transfer(transfer: Transfer, members: list[str]) -> Transfer:
    date = st.date_input("Date of expense", value=transfer.date, format=utils.DATE_INPUT_FMT)
    col_payer, col_quantity = st.columns(2)
    with col_payer:
        payer = st.selectbox("Who payed?", options=members, index=members.index(transfer.payer))
    with col_quantity:
        quantity = st.number_input("Quantity payed", value=transfer.quantity, min_value=0.01)
    recipient = st.selectbox("Who received the transfer?", options=members, index=members.index(transfer.recipient))

    return Transfer(payer=payer, quantity=quantity, recipient=recipient, date=date)


def _edit_entry_input(entry: LedgerEntry, members: list[str]) -> LedgerEntry:
    if isinstance(entry, Expense):
        if entry.quantity >= 0.0:
            return _input_expense(entry, members)
        return _input_reimbursement(entry, members)
    if isinstance(entry, Transfer):
        return _input_transfer(entry, members)
    raise ValueError("Unknown entry type")


@st.dialog(title="Are you sure?", icon="⚠️")
def _edit_entry(entry_index: int, updated_entry: LedgerEntry, ledger: Ledger) -> None:
    if st.button("💾 Confirm"):
        ledger.replace_entry(entry_index, updated_entry)
        ledger.save_to_file()
        st.rerun()
    if st.button("Cancel"):
        st.rerun()


@st.dialog(title="Are you sure?", icon="⚠️")
def _delete_entry(idx: int, ledger: Ledger) -> None:
    if st.button("❌ Delete"):
        ledger.delete_entry(index=idx)
        ledger.save_to_file()
        st.rerun()
    if st.button("Cancel"):
        st.rerun()


def edit_entry(ledger: Ledger) -> None:
    st.markdown("## Edit or delete an entry")
    st.markdown("### 🔍 Search entry")
    col0, col1 = st.columns(2)
    with col0:
        start_date = st.date_input("Start date", value=None, format=utils.DATE_INPUT_FMT)
        end_date = st.date_input("End date", value=None, format=utils.DATE_INPUT_FMT)
    with col1:
        filter_by_payer = st.selectbox("Filter by payer", options=ledger.members)
        filter_by_concept = st.text_input("Filter by concept", value=None)
    include_transfers = st.checkbox("Include transfers", value=True)

    entries = ledger.search(
        payer=filter_by_payer,
        concept=filter_by_concept,
        start_date=start_date,
        end_date=end_date,
        include_transfers=include_transfers,
    )

    entry_df = utils.build_entry_df(entries)

    st.markdown("### Select a row")
    event = st.dataframe(
        utils.format_entry_df(entry_df, ledger.members),
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        column_config={"Ledger Index": None},
    )

    selected_row = event.selection.rows[0] if event.selection.rows else None  # ty: ignore[unresolved-attribute]
    if selected_row is None:
        return

    st.markdown("### Modify data")
    entry_index = entry_df.at[selected_row, "Ledger Index"]
    selected_entry = ledger.get_entry(entry_index)
    updated_entry = _edit_entry_input(selected_entry, members=ledger.members)
    if st.button("💾 Edit entry!"):
        _edit_entry(entry_index, updated_entry, ledger)

    if st.button("❌ Delete selected entry!"):
        _delete_entry(entry_index, ledger=ledger)
