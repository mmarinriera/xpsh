import logging
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from expense_share import get_version
from expense_share.ledger import Expense
from expense_share.ledger import Ledger

logger = logging.getLogger(__name__)


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
    "-p", "--print-output", "print_output", is_flag=True, help="Show the ledger balance after adding the expense."
)
@click.option("--no-save", "no_save", is_flag=True, help="Do not update the file with the new expense.")
def add_expense(
    file_path: Path, payer: str, quantity: float, assignment: list[tuple[str, float]], print_output: bool, no_save: bool
) -> None:
    ledger = Ledger.from_file(file_path)
    logger.info("Ledger loaded from file")
    if not assignment:
        assignment = [(n, 1) for n in ledger.members]
    logger.info("No assignment provided. Equal parts assigned.")

    assignment_dict = {v[0]: v[1] for v in assignment}
    expense = Expense(payer=payer, quantity=quantity, assignment=assignment_dict)
    ledger.add_expense(expense)

    if print_output:
        _pretty_print_balance(ledger)

    if no_save:
        return

    ledger.save_ledger_to_file(file_path)
    logger.info("Updated ledger saved to file.")
