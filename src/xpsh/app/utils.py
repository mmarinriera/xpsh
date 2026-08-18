import itertools
from typing import Any

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


def build_entry_table_data(entries: list[IndexedLedgerEntry], members: list[str]) -> dict[str, list[Any]]:
    member_color_map = build_member_color_map(members, COLOR_PALETTE)

    date = []
    payer = []
    quantity = []
    concept = []
    assignment = []
    for _, entry in entries[::-1]:
        date.append(entry.date.strftime(DATE_FMT))
        payer.append(format_member_name(entry.payer, member_color_map))
        if isinstance(entry, Expense):
            quantity.append(
                f"{entry.quantity}"
                if entry.quantity >= 0.0
                else f":color[{-entry.quantity}]{{foreground='{COLOR_REIMBURSEMENT_TYPE}'}}"
            )
            concept.append(
                entry.concept
                if entry.quantity >= 0.0
                else f":color[{entry.concept}]{{foreground='{COLOR_REIMBURSEMENT_TYPE}'}}"
            )
        else:
            quantity.append(f":color[{entry.quantity}]{{foreground='{COLOR_TRANSFER_TYPE}'}}")
            concept.append(f":color[Transfer]{{foreground='{COLOR_TRANSFER_TYPE}'}}")

        assignment.append(format_assignment(entry, member_color_map))

    return {"Date": date, "Payer": payer, "Quantity": quantity, "Concept": concept, "Assignment/Recipient": assignment}
