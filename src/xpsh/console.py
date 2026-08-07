import logging

from rich.console import Console
from rich.table import Table
from rich.text import Text

from xpsh import Expense
from xpsh import Ledger
from xpsh import Transfer
from xpsh import utils
from xpsh.ledger import DATE_OUT_FMT

logger = logging.getLogger(__name__)
COLOR_PALETTE = [
    "deep_sky_blue2",
    "medium_purple1",
    "yellow",
    "orange_red1",
    "dark_cyan",
    "deep_pink3",
    "wheat1",
    "thistle1",
    "aquamarine1",
]


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


def print_balance(ledger: Ledger) -> None:
    """Pretty print ledger balance in terminal using rich text."""
    name_color_map = utils.build_member_color_map(ledger.members, COLOR_PALETTE)

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


def print_entries(ledger: Ledger, n_last_entries: int | None) -> None:
    """Pretty print ledger entries in terminal using rich text."""
    if n_last_entries is not None and n_last_entries < len(ledger.entries):
        entries = ledger.entries[:-n_last_entries]
    else:
        entries = ledger.entries

    name_color_map = utils.build_member_color_map(ledger.members, COLOR_PALETTE)

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


def print_examples(examples_dict: dict[str, str]) -> None:
    table = Table(title="Examples", title_justify="left", show_lines=True)
    table.add_column("Keyword", justify="right")
    table.add_column("Description", justify="right")
    for kw, descr in examples_dict.items():
        table.add_row(f"[bold cyan]{kw}[/bold cyan]", descr)

    console = Console()
    console.print(table)
    console.print("e.g. run: [bold purple]xpsh balance fellowship[/bold purple]")
