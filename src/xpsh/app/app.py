import os
from pathlib import Path

import streamlit as st

from xpsh import Ledger
from xpsh import get_version
from xpsh.app.add_entry import add_entry


def main() -> None:
    st.set_page_config(page_title="XPSH", page_icon="./icons/favicon.png")
    st.title("Expense Share!")
    st.badge(f"v{get_version()}", color="violet")

    file_path_str = os.getenv("XPSH_FILE_PATH")
    if file_path_str is None:
        st.error("Ledger path not specified.")
        return
    file_path = Path(file_path_str)
    members_str = os.getenv("XPSH_MEMBERS", default="")
    members = members_str.split(",")

    if not file_path.exists():
        if not members_str:
            st.error("Ledger path does not exist and no member names were passed to create new ledger.")
            return
        if len(members_str) < 2:
            st.error("Ledger path does not exist and less than 2 members were specified. Cannot create new ledger.")
            return

    ledger = Ledger(file_path=file_path, members=members, overwrite=False)

    tabs = ("Add Expense/Transfer", "Edit/Delete entry")

    active_tab = st.pills(
        "Choose action",
        tabs,
        key="active_tab",
        default=tabs[0],
    )

    if active_tab == tabs[0]:
        add_entry(ledger)
    else:
        return


if __name__ == "__main__":
    main()
