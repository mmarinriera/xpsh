import datetime
import logging
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from xpsh import get_version
from xpsh.ledger import DATE_OUT_FMT
from xpsh.ledger import Expense
from xpsh.ledger import Ledger
from xpsh.ledger import Transfer

logger = logging.getLogger(__name__)


class AssignmentDictRenderer:
    def __init__(self, assignment: dict[str, float], name_color_map: dict[str, str]):
        if any(name not in assignment for name in name_color_map):
            raise ValueError(f"Name color map does not match assignment names. {name_color_map}")
        self.assignment = assignment
        self.name_color_map = name_color_map

    def __rich__(self) -> Text:
        text_elements = []
        for name, fraction in self.assignment.items():
            color = self.name_color_map[name]
            text_elements.append(
                Text(": ").join(
                    [Text(name, style=f"bold {color}"), Text(f"{100 * fraction:.2f}%", style=f"italic {color}")]
                )
            )
        return Text(", ").join(text_elements)


def _pretty_print_balance(ledger: Ledger) -> None:
    balance = Table(title="Balance", title_justify="left")
    balance.add_column("Member", justify="right", style="cyan", no_wrap=True)
    balance.add_column("Total spent", justify="right")
    balance.add_column("Total paid", justify="right")
    balance.add_column("Owed", justify="right", style="magenta")

    for name, account in ledger.accounts.items():
        balance.add_row(name, str(account.spent), str(account.paid), str(account.owed))

    console = Console()
    console.print(balance)

    settle = Table(title="Transfers to settle", title_justify="left")
    settle.add_column("From", justify="right", style="cyan")
    settle.add_column("To", justify="right", style="cyan")
    settle.add_column("Quantity", justify="right", style="green")

    if not ledger.settle_transfers:
        console.print("[bold green]The balance is settled![/bold green]")
        return

    for transfer in ledger.settle_transfers:
        settle.add_row(transfer.payer, transfer.recipient, str(transfer.quantity))

    console.print(settle)


COLOR_PALETTE = ["purple", "yellow", "green", "red"]


def _pretty_print_entries(ledger: Ledger, n_last_entries: int | None) -> None:

    if n_last_entries is not None and n_last_entries < len(ledger.entries):
        entries = ledger.entries[:-n_last_entries]
    else:
        entries = ledger.entries

    colors = COLOR_PALETTE[: len(ledger.members)]
    name_color_map = dict(zip(ledger.members, colors))

    entry_table = Table(title="Entries", title_justify="left")
    entry_table.add_column("Type", justify="right")
    entry_table.add_column("Date", justify="right")
    entry_table.add_column("Paid by", justify="right")
    entry_table.add_column("Quantity", justify="right")
    entry_table.add_column("Assignment / Recipient", justify="right")

    for entry in entries:
        if isinstance(entry, Expense):
            entry_type = "[magenta]Expense[/magenta]"
            assignment = AssignmentDictRenderer(entry.assignment, name_color_map)
        elif isinstance(entry, Transfer):
            entry_type = "[cyan]Transfer[/cyan]"
            assignment = Text(entry.recipient, style=name_color_map[entry.recipient])
        else:
            raise ValueError(f"Unknown entry type (should never happen). {entry}.")

        entry_table.add_row(
            entry_type,
            entry.date.strftime(DATE_OUT_FMT),
            Text(entry.payer, style=name_color_map[entry.payer]),
            str(entry.quantity),
            assignment,
        )

    console = Console()
    console.print(entry_table)


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
@click.argument("file_path", type=click.Path(exists=True, resolve_path=True, path_type=Path))
def balance(file_path: Path) -> None:
    ledger = Ledger.from_file(file_path)
    logger.info("Ledger loaded from file")
    _pretty_print_balance(ledger)


@xpsh.command
@click.argument("file_path", type=click.Path(exists=True, resolve_path=True, path_type=Path))
@click.option("-n", "--n-last-entries", "n_last_entries", default=None, type=int, help="Show N most recent expenses.")
def expenses(file_path: Path, n_last_entries: int | None) -> None:
    ledger = Ledger.from_file(file_path)
    logger.info("Ledger loaded from file")

    _pretty_print_entries(ledger, n_last_entries)


@xpsh.command
@click.argument("file_path", type=click.Path(exists=True, resolve_path=True, path_type=Path))
@click.argument("payer", type=str)
@click.argument("quantity", type=float)
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
    file_path: Path,
    payer: str,
    quantity: float,
    assignment: list[tuple[str, float]],
    date_str: str | None,
    print_output: bool,
    no_save: bool,
) -> None:
    ledger = Ledger.from_file(file_path)
    logger.info("Ledger loaded from file")
    if not assignment:
        assignment = [(n, 1) for n in ledger.members]
    logger.info("No assignment provided. Equal parts assigned.")

    assignment_dict = {v[0]: v[1] for v in assignment}

    if date_str is not None:
        date = datetime.datetime.strptime(date_str, DATE_OUT_FMT).date()
    else:
        date = datetime.date.today()

    expense = Expense(payer=payer, quantity=quantity, assignment=assignment_dict, date=date)
    ledger.add_expense(expense)

    if print_output:
        _pretty_print_balance(ledger)

    if no_save:
        return

    ledger.save_ledger_to_file(file_path)
    logger.info("Updated ledger saved to file.")


@xpsh.command
@click.argument("file_path", type=click.Path(exists=True, resolve_path=True, path_type=Path))
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
    file_path: Path,
    payer: str,
    quantity: float,
    recipient: str,
    date_str: str | None,
    print_output: bool,
    no_save: bool,
) -> None:
    ledger = Ledger.from_file(file_path)
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

    ledger.save_ledger_to_file(file_path)
    logger.info("Updated ledger saved to file.")
