import itertools
import logging

import plotext as plt
from rich.ansi import AnsiDecoder
from rich.console import Console
from rich.console import ConsoleOptions
from rich.console import Group
from rich.console import RenderResult
from rich.jupyter import JupyterMixin
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from xpsh import Expense
from xpsh import Ledger
from xpsh import LedgerEntry
from xpsh import Transfer
from xpsh import utils
from xpsh.ledger import DATE_OUT_FMT

logger = logging.getLogger(__name__)

# Rich / plotext color 8-bit color codes
COLOR_PALETTE = [
    38,  # "deep_sky_blue2"
    141,  # "medium_purple1"
    3,  # "yellow"
    202,  # "orange_red1"
    36,  # "dark_cyan"
    162,  # "deep_pink3"
    229,  # "wheat1"
    225,  # "thistle1"
    122,  # "aquamarine1"
]

PLOT_PAD = (1, 2)


def _build_member_color_map(members: list[str], color_palette: list[int]) -> dict[str, str]:
    return {m: f"color({c})" for m, c in zip(members, itertools.cycle(color_palette))}


class AssignmentDictRenderer:
    def __init__(self, assignment: dict[str, float], name_color_map: dict[str, str]):
        if any(name not in name_color_map for name in assignment):
            raise ValueError(f"Name color map does not match assignment names. {assignment}")
        self.assignment = assignment
        self.name_color_map = name_color_map

    def __rich__(self) -> Text:
        text_elements = []
        for name, fraction in self.assignment.items():
            color = self.name_color_map[name]
            text_elements.append(
                Text("=", style=color).join(
                    [Text(name, style=color), Text(f"{100 * fraction:.2f}%", style=f"italic {color}")]
                )
            )
        return Text(", ").join(text_elements)


def _stacked_bar_plot(
    width: int, dates: list[str], series: dict[str, list[float]], colors: list[int], title: str
) -> str:
    plt.clf()
    labels = list(series.keys())
    y = list(series.values())
    plt.simple_stacked_bar(dates, y, labels=labels, colors=colors, width=width, title=title)
    out: str = plt.build()

    return out


class plotextMixin(JupyterMixin):
    def __init__(self, dates: list[str], series: dict[str, list[float]], title: str) -> None:
        self.decoder = AnsiDecoder()
        self.dates = dates
        self.series = series
        self.title = title

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        self.width = options.max_width or console.width
        colors = [c for _, c in zip(self.series.keys(), itertools.cycle(COLOR_PALETTE))]
        canvas = _stacked_bar_plot(
            self.width - 2 * PLOT_PAD[1], self.dates, self.series, title=self.title, colors=colors
        )
        self.rich_canvas = Group(*self.decoder.decode(canvas))
        yield self.rich_canvas


def _balance_history_plot(width: int, height: int, ledger: Ledger, title: str, colors: list[int]) -> str:

    t = plt.datetimes_to_string(ledger.history["total_expenses_t"])
    q = ledger.history["total_expenses_q"]

    logger.debug(f"w {width},h {height}")
    plt.date_form("d/m/Y")
    plt.clf()
    plt.plotsize(width=width, height=height)
    plt.theme("pro")
    plt.plot(t, q, label="Total expenses", color="white", marker="fhd")
    for m, c in zip(ledger.members, colors):
        t = plt.datetimes_to_string(ledger.history[f"account_{m}_t"])
        q = ledger.history[f"account_{m}_q"]
        plt.plot(t, q, label=f"Paid by {m}", color=c, marker="fhd")

    plt.title(title)
    out: str = plt.build()

    return out


class plotextMixinBalance(JupyterMixin):
    def __init__(self, ledger: Ledger, title: str) -> None:
        self.decoder = AnsiDecoder()
        self.ledger = ledger
        self.title = title

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        self.width = options.max_width or console.width
        self.height = options.max_height or console.height

        colors = [c for _, c in zip(self.ledger.members, itertools.cycle(COLOR_PALETTE))]
        canvas = _balance_history_plot(
            self.width - 2 * PLOT_PAD[1],
            (self.height - 2 * PLOT_PAD[0]) / 2,
            self.ledger,
            title=self.title,
            colors=colors,
        )
        self.rich_canvas = Group(*self.decoder.decode(canvas))
        yield self.rich_canvas


def print_balance(ledger: Ledger, plot: bool = False) -> None:
    """Pretty print ledger balance in terminal using rich text."""
    name_color_map = _build_member_color_map(ledger.members, COLOR_PALETTE)

    balance = Table(title="Balance", title_justify="left")
    balance.add_column("Member", justify="right", style="cyan", no_wrap=True)
    balance.add_column("Total spent", justify="right")
    balance.add_column("Total paid", justify="right")
    balance.add_column("Owed", justify="right", style="magenta")

    for name, account in ledger.accounts.items():
        color_owed = utils.COLOR_OWES if account.owed > 0 else utils.COLOR_IS_OWED
        balance.add_row(
            Text(name, style=name_color_map[name]),
            Text(f"{account.spent:.2f}"),
            Text(f"{account.paid:.2f}"),
            Text(f"{account.owed:.2f}", style=color_owed),
        )
    console = Console()
    console.print(balance)

    settle = Table(title="Transfers to settle", title_justify="left")
    settle.add_column("From", justify="right", style="cyan")
    settle.add_column("To", justify="right", style="cyan")
    settle.add_column("Quantity", justify="right", style="green")

    settle_transfers = ledger.settle_transfers

    if not settle_transfers:
        console.print("[bold green]The balance is settled![/bold green]")
        return

    for transfer in settle_transfers:
        settle.add_row(
            Text(transfer.payer, style=name_color_map[transfer.payer]),
            Text(transfer.recipient, style=name_color_map[transfer.recipient]),
            Text(f"{transfer.quantity:.2f}"),
        )

    console.print(settle)
    if plot:
        console.print(Padding(plotextMixinBalance(ledger, "Ledger balance history"), pad=PLOT_PAD))


def _build_expense_plot(entries: list[LedgerEntry], members: list[str], grouped: str) -> plotextMixin:
    if grouped == "day":
        key = lambda e: e.date.strftime("%d/%m/%Y")
    elif grouped == "month":
        key = lambda e: e.date.strftime("%m/%Y")
    else:
        raise ValueError("Invalid date grouping.")

    dates = []
    series: dict[str, list[float]] = {m: [] for m in members}

    for date, group in itertools.groupby([e for e in entries if isinstance(e, Expense)], key=key):
        aggregate = dict.fromkeys(members, 0.0)
        for entry in group:
            aggregate[entry.payer] += entry.quantity
        dates.append(date)
        for m, v in aggregate.items():
            series[m].append(v)

    return plotextMixin(dates=dates, series=series, title=f"Expense history grouped by {grouped}")


def print_entries(ledger: Ledger, n_last_entries: int | None, plot: bool, grouped: str) -> None:
    """Pretty print ledger entries in terminal using rich text."""
    if n_last_entries is not None and n_last_entries < len(ledger.entries):
        entries = ledger.entries[-n_last_entries:]
    else:
        entries = ledger.entries

    name_color_map = _build_member_color_map(ledger.members, COLOR_PALETTE)

    entry_table = Table(title="Entries", title_justify="left")
    entry_table.add_column("Type", justify="right")
    entry_table.add_column("Date", justify="right")
    entry_table.add_column("Paid by", justify="right")
    entry_table.add_column("Quantity", justify="right")
    entry_table.add_column("Concept", justify="right")
    entry_table.add_column("Assignment / Recipient", justify="left")

    for entry in entries:
        if isinstance(entry, Expense):
            entry_type = Text("Expense") if entry.quantity >= 0.0 else Text("Reimbursement")
            quantity = (
                Text(f"{entry.quantity:.2f}")
                if entry.quantity >= 0.0
                else Text(f"{-entry.quantity:.2f}", style=utils.COLOR_IS_OWED)
            )
            assignment = AssignmentDictRenderer(entry.assignment, name_color_map)
            concept = Text(entry.concept)
        elif isinstance(entry, Transfer):
            entry_type = Text("Transfer", style=utils.COLOR_TRANSFER_TYPE)
            quantity = Text(f"{entry.quantity:.2f}", style=utils.COLOR_TRANSFER_TYPE)
            assignment = Text(entry.recipient, style=name_color_map[entry.recipient])
            concept = Text("-")
        else:
            raise ValueError(f"Unknown entry type (should never happen). {entry}.")

        entry_table.add_row(
            entry_type,
            entry.date.strftime(DATE_OUT_FMT),
            Text(entry.payer, style=name_color_map[entry.payer]),
            quantity,
            concept,
            assignment,
        )

    console = Console()
    console.print(entry_table)
    if plot:
        console.print(Padding(_build_expense_plot(entries, ledger.members, grouped=grouped), pad=PLOT_PAD))


def print_examples(examples_dict: dict[str, str]) -> None:
    table = Table(title="Examples", title_justify="left", show_lines=True)
    table.add_column("Keyword", justify="right")
    table.add_column("Description", justify="right")
    for kw, descr in examples_dict.items():
        table.add_row(f"[bold cyan]{kw}[/bold cyan]", descr)

    console = Console()
    console.print(table)
    console.print("e.g. run: [bold purple]xpsh balance fellowship[/bold purple]")
