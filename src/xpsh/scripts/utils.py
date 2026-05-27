import itertools

COLOR_OWES = "red"
COLOR_IS_OWED = "green"
COLOR_TRANSFER_TYPE = "cyan"


def build_member_color_map(members: list[str], color_palette: list[str]) -> dict[str, str]:
    return dict(zip(members, itertools.cycle(color_palette)))
