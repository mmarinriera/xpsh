import itertools
from typing import Any

import numpy as np
import pandas as pd

from xpsh import Expense
from xpsh import IndexedLedgerEntry
from xpsh import LedgerEntry
from xpsh import Transfer

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
COLOR_REIMBURSEMENT_TYPE = "#00c817"

COLOR_OWES = "red"
COLOR_IS_OWED = "green"
COLOR_TRANSFER_TYPE = "cyan"


def build_member_color_map(members: list[str], color_palette: list[str]) -> dict[str, str]:
    return dict(zip(members, itertools.cycle(color_palette)))


def format_member_name(name: str, color_map: dict[str, str]) -> str:
    color = color_map[name]
    return f":color[**{name}**]{{foreground='{color}'}}"


def format_assignment(entry: LedgerEntry, member_color_map: dict[str, str]) -> str:
    if isinstance(entry, Transfer):
        return format_member_name(entry.recipient, member_color_map)
    if isinstance(entry, Expense):
        assignments_str = []
        for name, fraction in entry.assignment.items():
            color = member_color_map[name]
            assignments_str.append(f":color[**{name}**={100 * fraction:.2f}%]{{foreground='{color}'}}")
        return ", ".join(assignments_str)
    raise ValueError(f"Unknown entry type: {entry}")


def _build_table_data(entries: list[IndexedLedgerEntry]) -> dict[str, list[Any]]:
    entry_type = []
    date = []
    payer = []
    quantity = []
    concept = []
    assignment = []
    for _, entry in entries[::-1]:
        date.append(entry.date.strftime(DATE_FMT))
        payer.append(entry.payer)
        quantity.append(entry.quantity)
        if isinstance(entry, Expense):
            entry_type.append("Expense" if entry.quantity >= 0.0 else "Reimbursement")
            concept.append(entry.concept)
            assignment_str = [f"{n}={100 * v:.2f}%" for n, v in entry.assignment.items()]
            assignment.append(", ".join(assignment_str))
        elif isinstance(entry, Transfer):
            entry_type.append("Transfer")
            concept.append("-")
            assignment.append(entry.recipient)
        else:
            raise ValueError("Unknown entry type.")

    return {
        "Type": entry_type,
        "Date": date,
        "Payer": payer,
        "Quantity": quantity,
        "Concept": concept,
        "Assignment/Recipient": assignment,
    }


def build_entry_table_df(entries: list[IndexedLedgerEntry], members: list[str]) -> pd.DataFrame:
    member_color_map = build_member_color_map(members, COLOR_PALETTE)

    def format_entry_type(s: pd.Series) -> np.ndarray:
        if s.Type == "Transfer":
            color = f"color:{COLOR_TRANSFER_TYPE}"
        elif s.Type == "Reimbursement":
            color = f"color:{COLOR_REIMBURSEMENT_TYPE}"
        else:
            color = ""

        return np.array([color, "", "", color, color, ""])

    def format_name(value: str) -> str:
        return f"color:{member_color_map.get(value, '')}"

    def format_quantity(value: float) -> str:
        return f"color:{COLOR_REIMBURSEMENT_TYPE}" if value < 0.0 else ""

    df = pd.DataFrame(_build_table_data(entries))
    df = (
        df.style.format({"Quantity": "{:.2f}"})
        .apply(format_entry_type, axis=1)  # ty: ignore[unresolved-attribute]
        .map(format_quantity, subset="Quantity")
        .map(format_name, subset=["Payer", "Assignment/Recipient"])
    )
    return df
