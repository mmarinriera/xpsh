import streamlit as st

from xpsh import Ledger

from . import utils


def _entry_table_with_filters(ledger: Ledger) -> None:
    st.header("Search entries")

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

    st.table(utils.build_entry_table_data(entries, members=ledger.members))


def edit_entry(ledger: Ledger) -> None:
    _entry_table_with_filters(ledger)
