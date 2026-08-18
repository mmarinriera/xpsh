import itertools

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
