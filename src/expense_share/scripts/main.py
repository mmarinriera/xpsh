import logging
from pathlib import Path
from typing import Any

import click

from expense_share import get_version
from expense_share.ledger import Expense
from expense_share.ledger import Ledger

logger = logging.getLogger(__name__)


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
    click.echo(ledger)


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
    if not assignment:
        assignment = [(n, 1) for n in ledger.members]

    assignment_dict = {v[0]: v[1] for v in assignment}
    expense = Expense(payer=payer, quantity=quantity, distribution=assignment_dict)
    ledger.add_expense(expense)

    if print_output:
        click.echo(ledger)

    if no_save:
        return

    ledger.save_ledger_to_file(file_path)
