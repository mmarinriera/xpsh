import datetime
import logging
import sys
from pathlib import Path
from typing import Any

import click
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.text import Text

from xpsh import get_resource
from xpsh import get_version
from xpsh.ledger import DATE_OUT_FMT
from xpsh.ledger import Expense
from xpsh.ledger import Ledger
from xpsh.ledger import Transfer

from . import utils

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

EXAMPLE_LEDGERS = {"turtles": "tmnt.xpsh", "fellowship": "lotr.xpsh", "teveo": "tbo.xpsh"}
EXAMPLE_LEDGERS_DESCR = {
    "turtles": "Everyday shared expenses from a group of flatmates in NY.",
    "fellowship": "Shared expenses from a road trip through the country.",
    "teveo": "Shared expenses between a pair of twins.",
}


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


def _pretty_print_balance(ledger: Ledger) -> None:
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


def _pretty_print_entries(ledger: Ledger, n_last_entries: int | None) -> None:
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
            entry_type = Text("Expense")
            assignment = AssignmentDictRenderer(entry.assignment, name_color_map)
            concept = Text(entry.concept)
        elif isinstance(entry, Transfer):
            entry_type = Text("Transfer", style=utils.COLOR_TRANSFER_TYPE)
            assignment = Text(entry.recipient, style=name_color_map[entry.recipient])
            concept = Text("-")
        else:
            raise ValueError(f"Unknown entry type (should never happen). {entry}.")

        entry_table.add_row(
            entry_type,
            entry.date.strftime(DATE_OUT_FMT),
            Text(entry.payer, style=name_color_map[entry.payer]),
            Text(f"{entry.quantity:.2f}"),
            concept,
            assignment,
        )

    console = Console()
    console.print(entry_table)


def _resolve_input_path(input_str: str, exist_only: bool = True) -> Path:
    if input_str not in EXAMPLE_LEDGERS:
        input_path = Path(input_str)
        if not input_path.exists() and exist_only:
            logger.critical("Input file path doesn't exist. Aborting.")
            sys.exit(1)
        return input_path
    return get_resource(EXAMPLE_LEDGERS[input_str])


def print_version(ctx: click.Context, _: Any, value: Any) -> None:
    """Click print version."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(get_version())
    ctx.exit()


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
    "-v",
    "--version",
    is_flag=True,
    help="Print version and exit.",
    callback=print_version,
    expose_value=False,
    is_eager=True,
)
@click.option(
    "-d",
    "--debug",
    "debug_mode",
    is_flag=True,
    help="Enable debug mode.",
)
@click.pass_context
def xpsh(ctx: click.Context, debug_mode: bool) -> None:
    """Expense sharing tool"""
    ctx.ensure_object(dict)

    if debug_mode:
        logger.setLevel(level=logging.DEBUG)

    ctx.obj["debug"] = debug_mode


@xpsh.command
@click.argument("file_path", type=str)
@click.argument("members", nargs=-1, type=str)
@click.option("-f", "--force", "force", is_flag=True, help="Force overwriting of existing file in FILE_PATH.")
def create(file_path: str, members: list[str], force: bool) -> None:
    """
    Create new ledger.

    FILE_PATH is a valid path where the ledger data will be saved.
    If the file in FILE_PATH already exists, the program will not attempt to overwrite it and will abort,
    unless the -f/--force flag is passed.

    MEMBERS is a sequence of strings of arbitrary length, indicating the member names that should be
    included in the ledger.
    """
    resolved_path = _resolve_input_path(file_path, exist_only=False)

    if resolved_path.exists():
        if not force:
            logger.critical("Ledger file already exists. Aborting.")
            sys.exit(1)
        else:
            logger.info(f"Overwriting existing file in {file_path}")

    ledger = Ledger(file_path=resolved_path, members=members, overwrite=force)
    ledger.save_to_file()
    logger.info("New ledger saved to file.")


@xpsh.command
@click.argument("file_path", type=str)
def balance(file_path: str) -> None:
    """
    Calculate and display ledger balance.

    Transfers required to balance the ledger are also displayed.

    FILE_PATH is the path to the ledger file to be loaded.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.
    """
    resolved_path = _resolve_input_path(file_path)
    ledger = Ledger(file_path=resolved_path)
    logger.info("Ledger loaded from file")
    _pretty_print_balance(ledger)


@xpsh.command
@click.argument("file_path", type=str)
@click.option("-n", "--n-last-entries", "n_last_entries", default=None, type=int, help="Show N most recent expenses.")
def expenses(file_path: str, n_last_entries: int | None) -> None:
    """
    List and display ledger entries.

    FILE_PATH is the path to the ledger file to be loaded.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.

    """
    resolved_path = _resolve_input_path(file_path)
    ledger = Ledger(file_path=resolved_path)
    logger.info("Ledger loaded from file")

    _pretty_print_entries(ledger, n_last_entries)


@xpsh.command
def examples() -> None:
    """Displays the keywords to load different example files using the other CLI commands."""
    table = Table(title="Examples", title_justify="left", show_lines=True)
    table.add_column("Keyword", justify="right")
    table.add_column("Description", justify="right")
    for kw, descr in EXAMPLE_LEDGERS_DESCR.items():
        table.add_row(f"[bold cyan]{kw}[/bold cyan]", descr)

    console = Console()
    console.print(table)
    rprint("e.g. run: [bold purple]xpsh balance fellowship[/bold purple]")


@xpsh.command
@click.argument("file_path", type=str)
@click.argument("payer", type=str)
@click.argument("quantity", type=float)
@click.argument("concept", type=str)
@click.option(
    "-a",
    "--assignment",
    "assignment",
    type=(str, float),
    default=[],
    multiple=True,
    help="The part assigned to each person.",
)
@click.option(
    "-d", "--date", "date_str", type=str, default=None, help="Date in 'dd/mm/yyy' format (current day by default)."
)
@click.option(
    "-p", "--print-output", "print_output", is_flag=True, help="Show the ledger balance after adding the expense."
)
@click.option("--no-save", "no_save", is_flag=True, help="Do not update the file with the new expense.")
def add_expense(
    file_path: str,
    payer: str,
    quantity: float,
    concept: str,
    assignment: list[tuple[str, float]],
    date_str: str | None,
    print_output: bool,
    no_save: bool,
) -> None:
    """
    Add a new expense to a ledger.

    FILE_PATH is the path to the ledger file to be loaded.

    PAYER is the person that payed for the expense.

    QUANTITY is the quantity payed.

    CONCEPT is a short message to identify the expense (try to avoid including commas in the message).

    Use -a/--assignment option (multiple times if needed) to define how the expense is split between members.
    For example, if you want to split an expense 75%-25% between members "Zipi" and "Zape", pass the following:

    >>> -a Zipi 0.75 -a Zape 0.25

    Alternatively, the following would be equivalent and also valid
    (as long as the ratios between assignments stay the same):

    >>> -a Zipi 3 -a Zape 1

    >>> -a Zipi 75 -a Zape 25

    If no assignment is specified, the expense if split equally among all members by default.

    If not expense date is specified with -d/--date option, the current date is set by default.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.

    """
    resolved_path = _resolve_input_path(file_path)
    ledger = Ledger(file_path=resolved_path)
    logger.info("Ledger loaded from file")
    if not assignment:
        assignment = [(n, 1) for n in ledger.members]
    logger.info("No assignment provided. Equal parts assigned.")

    assignment_dict = {v[0]: v[1] for v in assignment}

    if date_str is not None:
        date = datetime.datetime.strptime(date_str, DATE_OUT_FMT).date()
    else:
        date = datetime.date.today()

    expense = Expense(payer=payer, quantity=quantity, concept=concept, assignment=assignment_dict, date=date)
    ledger.add_expense(expense)

    if print_output:
        _pretty_print_balance(ledger)

    if no_save:
        return

    ledger.save_to_file()
    logger.info("Updated ledger saved to file.")


@xpsh.command
@click.argument("file_path", type=str)
@click.argument("payer", type=str)
@click.argument("quantity", type=float)
@click.argument("recipient")
@click.option(
    "-d", "--date", "date_str", type=str, default=None, help="Date in 'dd/mm/yyy' format (current day by default)."
)
@click.option(
    "-p", "--print-output", "print_output", is_flag=True, help="Show the ledger balance after adding the expense."
)
@click.option("--no-save", "no_save", is_flag=True, help="Do not update the file with the new expense.")
def add_transfer(
    file_path: str,
    payer: str,
    quantity: float,
    recipient: str,
    date_str: str | None,
    print_output: bool,
    no_save: bool,
) -> None:
    """
    Add a new transfer between members to a ledger.

    FILE_PATH is the path to the ledger file to be loaded.

    PAYER is the person that is making the transfer.

    QUANTITY is the quantity payed.

    RECIPIENT is the person receiving the transfer.

    If not expense date is specified with -d/--date option, the current date is set by default.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.
    """
    resolved_path = _resolve_input_path(file_path)
    ledger = Ledger(file_path=resolved_path)
    logger.info("Ledger loaded from file")

    if date_str is not None:
        date = datetime.datetime.strptime(date_str, DATE_OUT_FMT).date()
    else:
        date = datetime.date.today()

    transfer = Transfer(payer=payer, quantity=quantity, recipient=recipient, date=date)
    ledger.add_transfer(transfer)

    if print_output:
        _pretty_print_balance(ledger)

    if no_save:
        return

    ledger.save_to_file()
    logger.info("Updated ledger saved to file.")
