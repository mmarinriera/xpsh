import itertools

from xpsh import Expense
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
