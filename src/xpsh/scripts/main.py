import datetime
import logging
from enum import Enum
from pathlib import Path
from typing import Annotated
from typing import Any

import click
import typer

from xpsh import Expense
from xpsh import Ledger
from xpsh import LedgerEntry
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


class GroupedByPeriod(Enum):
    day = "day"
    month = "month"


def _resolve_input_path(input_str: str, exist_only: bool = True) -> Path:
    if input_str not in EXAMPLE_LEDGERS:
        input_path = Path(input_str)
        if not input_path.exists() and exist_only:
            logger.critical("Input file path doesn't exist. Aborting.")
            raise typer.Exit(1)
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

    try:
        ledger = Ledger(file_path=resolved_path)
    except ValueError as e:
        logger.critical(f"{e} Aborting.")
        raise typer.Exit(1)

    if not assignment:
        assignment = [(n, 1) for n in ledger.members]
        logger.info("No assignment provided. Equal parts assigned.")

    assignment_dict = {v[0]: v[1] for v in assignment}

    if date_str is not None:
        date = datetime.datetime.strptime(date_str, DATE_OUT_FMT).date()
    else:
        logger.info("Using current date.")
        date = datetime.date.today()

    try:
        expense = Expense(payer=payer, quantity=quantity, concept=concept, assignment=assignment_dict, date=date)
        ledger.add_expense(expense)
    except ValueError as e:
        logger.critical(f"{e} Aborting.")
        raise typer.Exit(1)

    if print_output:
        console.print_balance(ledger)

    if no_save:
        return

    ledger.save_to_file()
    logger.info("Updated ledger saved to file.")


def _build_updated_expense(
    current_entry: Expense,
    payer: str,
    quantity: float,
    concept: str | None,
    assignment: list[tuple[str, float]] | None,
    date: datetime.date,
) -> Expense:
    if concept is None:
        concept = current_entry.concept
    assignment_dict = {n: v for n, v in assignment} if assignment else current_entry.assignment

    # Ensure that a reimbursment entry cannot be switched into an expense by making the quantity positive.
    if current_entry.quantity < 0.0 and quantity > 0.0:
        quantity = -quantity

    return Expense(payer=payer, quantity=quantity, concept=concept, assignment=assignment_dict, date=date)


def _build_updated_transfer(
    current_entry: Transfer,
    payer: str,
    quantity: float,
    recipient: str | None,
    date: datetime.date,
) -> Transfer:
    if recipient is None:
        recipient = current_entry.recipient
    return Transfer(payer=payer, quantity=quantity, recipient=recipient, date=date)


def _build_updated_entry(
    current_entry: LedgerEntry,
    payer: str | None,
    quantity: float | None,
    concept: str | None,
    assignment: list[tuple[str, float]] | None,
    recipient: str | None,
    date_str: str | None,
) -> LedgerEntry:
    if payer is None:
        payer = current_entry.payer

    if quantity is None:
        quantity = current_entry.quantity

    date = datetime.datetime.strptime(date_str, DATE_OUT_FMT).date() if date_str is not None else current_entry.date

    if isinstance(current_entry, Expense):
        new_entry: LedgerEntry = _build_updated_expense(current_entry, payer, quantity, concept, assignment, date)

    if isinstance(current_entry, Transfer):
        new_entry = _build_updated_transfer(current_entry, payer, quantity, recipient, date)

    return new_entry


def print_version(ctx: click.Context, _: Any, value: Any) -> None:
    """Click print version."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(get_version())
    ctx.exit()


xpsh = typer.Typer()


def version_callback(value: bool) -> None:
    if value:
        print(get_version())
        raise typer.Exit()


@xpsh.callback()
def cli_callback(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("-v", "--version", callback=version_callback, is_eager=True, help="Show version and exit.")
    ] = False,
    debug_mode: Annotated[bool, typer.Option("-d", "--debug", help="Enable DEBUG logging.")] = False,
) -> None:
    """Expense sharing tool"""
    ctx.ensure_object(dict)

    if debug_mode:
        set_logging_level(logging.DEBUG)

    ctx.obj["debug"] = debug_mode


@xpsh.command()
def create(
    file_path: Annotated[str, typer.Argument(help="File path where the ledger data will be saved.")],
    members: Annotated[list[str], typer.Argument(help="Member names that should be included in the ledger.")],
    force: Annotated[
        bool, typer.Option("-f", "--force", help="Force overwriting of existing file in FILE_PATH.")
    ] = False,
) -> None:
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
            raise typer.Exit(1)
        logger.info(f"Overwriting existing file in {file_path}")

    try:
        ledger = Ledger(file_path=resolved_path, members=members, overwrite=force)
    except ValueError as e:
        logger.critical(f"{e} Aborting.")
        raise typer.Exit(1)

    ledger.save_to_file()
    logger.info("New ledger saved to file.")


@xpsh.command()
def balance(
    file_path: Annotated[str, typer.Argument(help="Path to the ledger file.")],
    graph: Annotated[bool, typer.Option("-g", "--graph", help="Show graph of balance history.")] = False,
) -> None:
    """
    Calculate and display ledger balance.

    Transfers required to balance the ledger are also displayed.

    FILE_PATH is the path to the ledger file to be loaded.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.
    """
    resolved_path = _resolve_input_path(file_path)

    try:
        ledger = Ledger(file_path=resolved_path, track_history=graph)
    except ValueError as e:
        logger.critical(f"{e} Aborting.")
        raise typer.Exit(1)

    console.print_balance(ledger, graph)


@xpsh.command()
def expenses(
    file_path: Annotated[str, typer.Argument(help="Path to the ledger file.")],
    n_last_entries: Annotated[
        int | None, typer.Option("-n", "--n-last-entries", help="Show N most recent expenses.")
    ] = None,
    graph: Annotated[bool, typer.Option("-g", "--graph", help="Show stacked bar graph of expense history.")] = False,
    grouped: Annotated[
        GroupedByPeriod, typer.Option("--grouped-by", help="How to aggregate expenses in graph.")
    ] = GroupedByPeriod.month,
) -> None:
    """
    List and display ledger entries.

    FILE_PATH is the path to the ledger file to be loaded.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.

    """
    resolved_path = _resolve_input_path(file_path)

    try:
        ledger = Ledger(file_path=resolved_path)
    except ValueError as e:
        logger.critical(f"{e} Aborting.")
        raise typer.Exit(1)

    console.print_expenses(ledger, n_last_entries, graph, grouped.value)


@xpsh.command()
def examples() -> None:
    """Displays the keywords to load different example files using the other CLI commands."""
    console.print_examples(EXAMPLE_LEDGERS_DESCR)


@xpsh.command()
def search(
    file_path: Annotated[str, typer.Argument(help="Path to the ledger file.")],
    payer: Annotated[str | None, typer.Option("-p", "--payer", help="Filter entries by payer.")] = None,
    concept: Annotated[str | None, typer.Option("-c", "--concept", help="Filter entries by concept.")] = None,
    start_date: Annotated[
        str | None, typer.Option("-f", "--from", help="Filter entries later than date ('dd/mm/yyy' format).")
    ] = None,
    end_date: Annotated[
        str | None, typer.Option("-u", "--until", help="Filter entries earlier than date ('dd/mm/yyy' format).")
    ] = None,
    include_transfers: Annotated[
        bool, typer.Option("-t", "--include-transfers", help="Include transfers in the search.")
    ] = False,
) -> None:
    """
    Search a ledger for an entry.

    FILE_PATH is the path to the ledger file to be loaded.

    HINT: You can load one of the example ledgers by passing a keyword instead of FILE_PATH.

    Run `xpsh examples` to check the available examples.

    """
    resolved_path = _resolve_input_path(file_path)
    try:
        ledger = Ledger(file_path=resolved_path)

        entries = ledger.search(
            payer=payer,
            concept=concept,
            start_date=datetime.datetime.strptime(start_date, DATE_OUT_FMT).date() if start_date is not None else None,
            end_date=datetime.datetime.strptime(end_date, DATE_OUT_FMT).date() if end_date is not None else None,
            include_transfers=include_transfers,
        )
    except ValueError as e:
        logger.critical(f"{e} Aborting.")
        raise typer.Exit(1)
    console.print_search_entries(ledger, entries)


@xpsh.command()
def add_expense(
    file_path: Annotated[str, typer.Argument(help="Path to the ledger file.")],
    payer: Annotated[str, typer.Argument(help="Who payed for the expense.")],
    quantity: Annotated[float, typer.Argument(help="Quantity payed.")],
    concept: Annotated[str, typer.Argument(help="What was the expense for.")],
    assignment: Annotated[
        list[tuple[str, float]],
        typer.Option("-a", "--assignment", default_factory=list, help="The part assigned to each person."),
    ],
    date_str: Annotated[
        str | None, typer.Option("-d", "--date", help="Date in 'dd/mm/yyy' format (current day by default).")
    ] = None,
    print_output: Annotated[bool, typer.Option("-p", help="Show the ledger balance after adding the expense.")] = False,
    no_save: Annotated[bool, typer.Option(help="Do not update the file with the new expense.")] = False,
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


@xpsh.command()
def add_reimbursement(
    file_path: Annotated[str, typer.Argument(help="Path to the ledger file.")],
    recipient: Annotated[str, typer.Argument(help="Who received the reimbursement.")],
    quantity: Annotated[float, typer.Argument(help="Quantity reimbursed.")],
    concept: Annotated[str, typer.Argument(help="What was the reimbursement for.")],
    assignment: Annotated[
        list[tuple[str, float]],
        typer.Option("-a", "--assignment", default_factory=list, help="The part assigned to each person."),
    ],
    date_str: Annotated[
        str | None, typer.Option("-d", "--date", help="Date in 'dd/mm/yyy' format (current day by default).")
    ] = None,
    print_output: Annotated[bool, typer.Option("-p", help="Show the ledger balance after adding the expense.")] = False,
    no_save: Annotated[bool, typer.Option(help="Do not update the file with the new expense.")] = False,
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


@xpsh.command()
def add_transfer(
    file_path: Annotated[str, typer.Argument(help="Path to the ledger file.")],
    payer: Annotated[str, typer.Argument(help="Who made the transfer.")],
    quantity: Annotated[float, typer.Argument(help="Quantity transferred.")],
    recipient: Annotated[str, typer.Argument(help="Who received the transfer.")],
    date_str: Annotated[
        str | None, typer.Option("-d", "--date", help="Date in 'dd/mm/yyy' format (current day by default).")
    ] = None,
    print_output: Annotated[bool, typer.Option("-p", help="Show the ledger balance after adding the expense.")] = False,
    no_save: Annotated[bool, typer.Option(help="Do not update the file with the new expense.")] = False,
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

    if date_str is not None:
        date = datetime.datetime.strptime(date_str, DATE_OUT_FMT).date()
    else:
        date = datetime.date.today()

    try:
        ledger = Ledger(file_path=resolved_path)
        transfer = Transfer(payer=payer, quantity=quantity, recipient=recipient, date=date)
        ledger.add_transfer(transfer)
    except ValueError as e:
        logger.critical(f"{e} Aborting.")
        raise typer.Exit(1)

    if print_output:
        console.print_balance(ledger)

    if no_save:
        return

    ledger.save_to_file()
    logger.info("Updated ledger saved to file.")


@xpsh.command()
def delete_entry(
    file_path: Annotated[str, typer.Argument(help="Path to the ledger file.")],
    index: Annotated[int, typer.Argument(help="Entry index.")],
    yes: Annotated[bool, typer.Option("-y", help="Confirm deletion of entry without input prompt.")] = False,
) -> None:
    """
    Delete an entry from the ledger.

    FILE_PATH is the path to the ledger file to be loaded.

    INDEX is the number used to identify the entry.

    TIP! Use "xpsh expenses" or "xpsh search" to find which index corresponds to the entry you are looking for.

    """
    resolved_path = _resolve_input_path(file_path)

    try:
        ledger = Ledger(file_path=resolved_path)
        entry = ledger.get_entry(index)
    except ValueError as e:
        logger.critical(f"{e} Aborting.")
        raise typer.Exit(1)

    console.print_single_entry(ledger, index, entry)
    confirm: str = click.prompt("Are you sure you want to delete this entry?[y|n]", default="n") if not yes else "y"

    if confirm.lower() != "y":
        logger.info("Action cancelled.")
        raise typer.Exit(0)

    ledger.delete_entry(index)
    ledger.save_to_file()
    logger.info("Entry deleted from ledger.")
    logger.warning("Entries indexing has changed after changed. Check indexes before deleting the next entry!")


@xpsh.command()
def edit_entry(
    file_path: Annotated[str, typer.Argument(help="Path to the ledger file.")],
    index: Annotated[int, typer.Argument(help="Entry index.")],
    payer: Annotated[str | None, typer.Option("-p", help="Edit the payer.")] = None,
    quantity: Annotated[float | None, typer.Option("-q", help="Edit the quantity.")] = None,
    concept: Annotated[
        str | None, typer.Option("-c", help="Edit the concept (expense and reimbursement only).")
    ] = None,
    recipient: Annotated[str | None, typer.Option("-r", help="Edit the recipient (transfers only).")] = None,
    assignment: Annotated[list[tuple[str, float]] | None, typer.Option("-a", help="Edit the assignment.")] = None,
    date_str: Annotated[str | None, typer.Option("-d", "--date", help="Edit the date ('dd/mm/yyy' format).")] = None,
    yes: Annotated[bool, typer.Option("-y", help="Confirm deletion of entry without input prompt.")] = False,
) -> None:
    """
    Edit an entry from the ledger.

    FILE_PATH is the path to the ledger file to be loaded.

    INDEX is the number used to identify the entry.

    TIP! Use "xpsh expenses" or "xpsh search" to find which index corresponds to the entry you are looking for.

    """
    resolved_path = _resolve_input_path(file_path)
    try:
        ledger = Ledger(file_path=resolved_path)
        entry = ledger.get_entry(index)
    except ValueError as e:
        logger.critical(f"{e} Aborting.")
        raise typer.Exit(1)

    new_entry = _build_updated_entry(
        entry,
        payer=payer,
        quantity=quantity,
        concept=concept,
        assignment=assignment,
        recipient=recipient,
        date_str=date_str,
    )

    console.print_entry_diff(entry, new_entry)

    confirm: str = click.prompt("Are you sure you want to edit this entry?[y|n]", default="n") if not yes else "y"
    if confirm.lower() != "y":
        logger.info("Action cancelled.")
        raise typer.Exit(0)

    ledger.replace_entry(index, new_entry)
    ledger.save_to_file()
    logger.info("Entry modified.")
