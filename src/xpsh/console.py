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
from xpsh.ledger import IndexedLedgerEntry

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


class plotextMixin(JupyterMixin):
    def __init__(self, plot_canvas: str) -> None:
        self.decoder = AnsiDecoder()
        self.canvas = plot_canvas

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        self.rich_canvas = Group(*self.decoder.decode(self.canvas))
        yield self.rich_canvas


def _print_entries_table(entries: list[IndexedLedgerEntry], color_map: dict[str, str], title: str = "Entries") -> Table:
    entry_table = Table(title=title, title_justify="left", title_style="bold")
    entry_table.add_column("Index", justify="right")
    entry_table.add_column("Type", justify="right")
    entry_table.add_column("Date", justify="right")
    entry_table.add_column("Paid by", justify="right")
    entry_table.add_column("Quantity", justify="right")
    entry_table.add_column("Concept", justify="right")
    entry_table.add_column("Assignment / Recipient", justify="left")

    for idx, entry in entries:
        if isinstance(entry, Expense):
            entry_type = Text("Expense") if entry.quantity >= 0.0 else Text("Reimbursement")
            quantity = (
                Text(f"{entry.quantity:.2f}")
                if entry.quantity >= 0.0
                else Text(f"{-entry.quantity:.2f}", style=utils.COLOR_IS_OWED)
            )
            assignment = AssignmentDictRenderer(entry.assignment, color_map)
            concept = Text(entry.concept)
        elif isinstance(entry, Transfer):
            entry_type = Text("Transfer", style=utils.COLOR_TRANSFER_TYPE)
            quantity = Text(f"{entry.quantity:.2f}", style=utils.COLOR_TRANSFER_TYPE)
            assignment = Text(entry.recipient, style=color_map[entry.recipient])
            concept = Text("-")
        else:
            raise ValueError(f"Unknown entry type (should never happen). {entry}.")

        entry_table.add_row(
            str(idx),
            entry_type,
            entry.date.strftime(DATE_OUT_FMT),
            Text(entry.payer, style=color_map[entry.payer]),
            quantity,
            concept,
            assignment,
        )
    return entry_table


def _balance_history_plot(width: int, height: int, ledger: Ledger, title: str) -> str:
    t = plt.datetimes_to_string(ledger.history["dates"])
    exp = ledger.history["total_expenses"]
    colors = [c for _, c in zip(ledger.members, itertools.cycle(COLOR_PALETTE))]

    plt.date_form("d/m/Y")
    plt.clf()
    plt.plotsize(width=width, height=height)
    plt.theme("pro")
    plt.plot(t, exp, label="Total expenses", color="white", marker="fhd")
    for m, c in zip(ledger.members, colors):
        q = ledger.history[f"account_{m}_paid"]
        if not t:
            continue

        plt.plot(t, q, label=f"Paid by {m}", color=c, marker="fhd")

    plt.title(title)
    out: str = plt.build()

    return out


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
    if not plot:
        return

    canvas = _balance_history_plot(
        console.width - 2 * PLOT_PAD[1],
        (console.height - 2 * PLOT_PAD[0]) // 2,
        ledger,
        title="Ledger balance history",
    )

    console.print(Padding(plotextMixin(plot_canvas=canvas), pad=PLOT_PAD))


def _stacked_bar_plot(width: int, dates: list[str], series: dict[str, list[float]], title: str) -> str:
    colors = [c for _, c in zip(series.keys(), itertools.cycle(COLOR_PALETTE))]

    plt.clf()
    labels = list(series.keys())
    y = list(series.values())
    plt.simple_stacked_bar(dates, y, labels=labels, colors=colors, width=width, title=title)
    out: str = plt.build()

    return out


def _build_expense_plot(width: int, entries: list[LedgerEntry], members: list[str], grouped: str) -> plotextMixin:
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

    canvas = _stacked_bar_plot(
        width=width - 2 * PLOT_PAD[1], dates=dates, series=series, title=f"Expense history grouped by {grouped}"
    )
    return plotextMixin(plot_canvas=canvas)


def print_expenses(ledger: Ledger, n_last_entries: int | None, plot: bool, grouped: str) -> None:
    """Pretty print ledger entries in terminal using rich text."""
    if n_last_entries is not None and n_last_entries < len(ledger.entries):
        idx_entries = ledger.indexed_entries[-n_last_entries:]
    else:
        idx_entries = ledger.indexed_entries

    name_color_map = _build_member_color_map(ledger.members, COLOR_PALETTE)

    console = Console()
    console.print(_print_entries_table(idx_entries, name_color_map))
    if plot:
        console.print(
            Padding(
                _build_expense_plot(console.width, [e for _, e in idx_entries], ledger.members, grouped=grouped),
                pad=PLOT_PAD,
            )
        )


def print_search_entries(ledger: Ledger, entries: list[IndexedLedgerEntry]) -> None:
    name_color_map = _build_member_color_map(ledger.members, COLOR_PALETTE)
    console = Console()
    if not entries:
        console.print("No entries found matching the criteria.")
        return

    console.print(_print_entries_table(entries, name_color_map))


def print_single_entry(ledger: Ledger, index: int, entry: LedgerEntry) -> None:
    name_color_map = _build_member_color_map(ledger.members, COLOR_PALETTE)
    console = Console()
    console.print(_print_entries_table([(index, entry)], name_color_map, title="Selected entry"))


def print_entry_diff(entry: LedgerEntry, new_entry: LedgerEntry) -> None:
    console = Console()
    console.print(entry)
    console.print(new_entry)


def print_examples(examples_dict: dict[str, str]) -> None:
    table = Table(title="Examples", title_justify="left", show_lines=True)
    table.add_column("Keyword", justify="right")
    table.add_column("Description", justify="right")
    for kw, descr in examples_dict.items():
        table.add_row(f"[bold cyan]{kw}[/bold cyan]", descr)

    console = Console()
    console.print(table)
    console.print("e.g. run: [bold purple]xpsh balance fellowship[/bold purple]")
