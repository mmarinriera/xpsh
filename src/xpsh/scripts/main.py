import datetime
import logging
import sys
from pathlib import Path
from typing import Any

import click

from xpsh import Expense
from xpsh import Ledger
from xpsh import Transfer
from xpsh import console
from xpsh import get_resource
from xpsh import get_version
from xpsh import set_logging_level
from xpsh.ledger import DATE_OUT_FMT

logger = logging.getLogger(__name__)


EXAMPLE_LEDGERS = {"turtles": "tmnt.xpsh", "fellowship": "lotr.xpsh", "teveo": "tbo.xpsh"}
EXAMPLE_LEDGERS_DESCR = {
    "turtles": "Everyday shared expenses from a group of flatmates in NY.",
    "fellowship": "Shared expenses from a road trip through the country.",
    "teveo": "Shared expenses between a pair of twins.",
}


def _resolve_input_path(input_str: str, exist_only: bool = True) -> Path:
    if input_str not in EXAMPLE_LEDGERS:
        input_path = Path(input_str)
        if not input_path.exists() and exist_only:
            logger.critical("Input file path doesn't exist. Aborting.")
            sys.exit(1)
        return input_path
    return get_resource(EXAMPLE_LEDGERS[input_str])


def _add_expense(
    file_path: str,
    payer: str,
    quantity: float,
    concept: str,
    assignment: list[tuple[str, float]],
    date_str: str | None,
    print_output: bool,
    no_save: bool,
) -> None:
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
        console.print_balance(ledger)

    if no_save:
        return

    ledger.save_to_file()
    logger.info("Updated ledger saved to file.")


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
        set_logging_level(logging.DEBUG)

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
@click.option("-g", "--graph", "graph", is_flag=True, help="Show graph of balance history.")
def balance(file_path: str, graph: bool) -> None:
    """
    Calculate and display ledger balance.

    Transfers required to balance the ledger are also displayed.

    FILE_PATH is the path to the ledger file to be loaded.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.
    """
    resolved_path = _resolve_input_path(file_path)
    ledger = Ledger(file_path=resolved_path, track_history=graph)
    logger.info("Ledger loaded from file")
    console.print_balance(ledger, graph)


@xpsh.command
@click.argument("file_path", type=str)
@click.option("-n", "--n-last-entries", "n_last_entries", default=None, type=int, help="Show N most recent expenses.")
@click.option("-g", "--graph", "graph", is_flag=True, help="Show stacked bar graph of expense history.")
@click.option(
    "--grouped-by",
    "grouped",
    type=click.Choice(["day", "month"]),
    default="month",
    help="How to aggregate expenses in graph.",
)
def expenses(file_path: str, n_last_entries: int | None, graph: bool, grouped: str) -> None:
    """
    List and display ledger entries.

    FILE_PATH is the path to the ledger file to be loaded.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.

    """
    resolved_path = _resolve_input_path(file_path)
    ledger = Ledger(file_path=resolved_path)
    logger.info("Ledger loaded from file")

    console.print_entries(ledger, n_last_entries, graph, grouped)


@xpsh.command
def examples() -> None:
    """Displays the keywords to load different example files using the other CLI commands."""
    console.print_examples(EXAMPLE_LEDGERS_DESCR)


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

    If no assignment is specified, the expense is split equally among all members by default.

    If not expense date is specified with -d/--date option, the current date is set by default.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.

    """
    _add_expense(
        file_path=file_path,
        payer=payer,
        quantity=quantity,
        concept=concept,
        assignment=assignment,
        date_str=date_str,
        print_output=print_output,
        no_save=no_save,
    )


@xpsh.command
@click.argument("file_path", type=str)
@click.argument("recipient", type=str)
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
    "-p", "--print-output", "print_output", is_flag=True, help="Show the ledger balance after adding the reimbursement."
)
@click.option("--no-save", "no_save", is_flag=True, help="Do not update the file with the new entry.")
def add_reimbursement(
    file_path: str,
    recipient: str,
    quantity: float,
    concept: str,
    assignment: list[tuple[str, float]],
    date_str: str | None,
    print_output: bool,
    no_save: bool,
) -> None:
    """
    Add a new reimbursement to a ledger.

    FILE_PATH is the path to the ledger file to be loaded.

    RECIPIENT is the person that received the reimbursement.

    QUANTITY is the quantity received.

    CONCEPT is a short message to identify the entry (try to avoid including commas in the message).

    In the context of the ledger, a reimbursement entry is simply an expense entry with a negative quantity.

    Use -a/--assignment option (multiple times if needed) to define how the reimbursement is split between members.
    For example, if you want to split it 75%-25% between members "Zipi" and "Zape", pass the following:

    >>> -a Zipi 0.75 -a Zape 0.25

    Alternatively, the following would be equivalent and also valid
    (as long as the ratios between assignments stay the same):

    >>> -a Zipi 3 -a Zape 1

    >>> -a Zipi 75 -a Zape 25

    If no assignment is specified, the reimbursement is split equally among all members by default.

    If not expense date is specified with -d/--date option, the current date is set by default.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.

    """
    _add_expense(
        file_path=file_path,
        payer=recipient,
        quantity=-quantity,
        concept=concept,
        assignment=assignment,
        date_str=date_str,
        print_output=print_output,
        no_save=no_save,
    )


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
        console.print_balance(ledger)

    if no_save:
        return

    ledger.save_to_file()
    logger.info("Updated ledger saved to file.")
