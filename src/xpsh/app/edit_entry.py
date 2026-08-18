import streamlit as st

from xpsh import Expense
from xpsh import Ledger

from . import utils


def _entry_table_with_filters(ledger: Ledger) -> None:
    st.header("Search entries")
    member_color_map = utils.build_member_color_map(ledger.members, utils.COLOR_PALETTE)

    col0, col1 = st.columns(2)

    with col0:
        start_date = st.date_input("Start date", value=None, format="DD/MM/YYYY")
        end_date = st.date_input("End date", value=None, format="DD/MM/YYYY")
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

    date = []
    payer = []
    quantity = []
    concept = []
    assignment = []
    for _, entry in entries[::-1]:
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


def edit_entry(ledger: Ledger) -> None:
    _entry_table_with_filters(ledger)
