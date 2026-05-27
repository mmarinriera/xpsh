import itertools

COLOR_PALETTE = ["deep_sky_blue2", "purple", "yellow", "orange_red1", "dark_cyan", "pink"]
COLOR_OWES = "red"
COLOR_IS_OWED = "green"
COLOR_TRANSFER_TYPE = "cyan"


def build_member_color_map(members: list[str]) -> dict[str, str]:
    return dict(zip(members, itertools.cycle(COLOR_PALETTE)))
