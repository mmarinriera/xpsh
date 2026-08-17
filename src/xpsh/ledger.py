import datetime
import logging
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Protocol

from filelock import FileLock

logger = logging.getLogger(__name__)

DATE_OUT_FMT = "%d/%m/%Y"
LOCK_TIMEOUT_SECONDS = 10


@dataclass
class Account:
    """
    Ledger member account.

    Attributes:
        name(str): Account name.
        spent(float): Total quantity spent.
        paid(float): Total quantity paid.
        owed(float): Quantity owed to other accounts, calculated as `spent` - `paid`.
            Negative values indicate that money is owed to the account.

    """

    name: str
    spent: float = 0.0
    paid: float = 0.0

    @property
    def owed(self) -> float:
        return self.spent - self.paid


class LedgerEntry(Protocol):
    payer: str
    quantity: float
    date: datetime.date

    def to_output(self) -> str:
        """
        Formats entry data to be saved in an output file.

        Returns:
            Formatted entry data.

        """
        raise NotImplementedError


@dataclass
class Expense:
    """
    Expense entry in the ledger.

    Attributes:
        payer(str): Account that payed for the expense.
        quantity(float): Quantity payed.
        concept(str): Short message to identify the expense.
        assignment(dict[str,  float]): How the expense is split between different accounts.
        date(datetime.date): Date of the expense.

    """

    payer: str
    quantity: float
    concept: str
    assignment: dict[str, float]
    date: datetime.date

    def __post_init__(self) -> None:
        if sum(list(self.assignment.values())) == 1.0:
            return

        logger.info("Assignment weights doesn't add up to 1, normalising.")
        total = sum(list(self.assignment.values()))
        for name, value in self.assignment.items():
            self.assignment[name] = value / total

    def __repr__(self) -> str:
        return f"Expense | Payed on: {self.date.strftime(DATE_OUT_FMT)}, by: {self.payer}, quantity: {self.quantity}, for: {self.concept}. Assignment: {self.assignment}."

    def to_output(self) -> str:
        """
        Formats expense data to be saved in an output file.

        Returns:
            Formatted expense data.

        """
        assignment_out = [f"{n}:{d}" for n, d in self.assignment.items()]
        concept_out = self.concept.replace(",", "")
        return ",".join(
            [self.date.strftime(DATE_OUT_FMT), self.payer, str(self.quantity), concept_out] + assignment_out
        )


@dataclass
class Transfer:
    """
    Transfer between two accounts.

    Attributes:
        payer(str): Account that payed for the expense.
        quantity(float): Quantity payed.
        recipient(str): Account that received the transfer.
        date(datetime.date): Date of the expense.

    """

    payer: str
    quantity: float
    recipient: str
    date: datetime.date = datetime.date.today()

    def __post_init__(self) -> None:
        if self.payer == self.recipient:
            raise ValueError("Payer and recipient must be different.")

    def __repr__(self) -> str:
        return f"Transfer '{self.payer}' -> '{self.recipient}': {self.quantity}."

    def to_output(self) -> str:
        """
        Formats transfer data to be saved in an output file.

        Returns:
            Formatted transfer data.

        """
        return ",".join([self.date.strftime(DATE_OUT_FMT), self.payer, str(self.quantity), self.recipient])


IndexedLedgerEntry = tuple[int, LedgerEntry]


def _member_list_sanity_check(members: list[str]) -> None:
    """Ensures there's more than one member, and there's no duplicate names."""
    if len(members) <= 1:
        raise ValueError(f"Include at least two members. {members}")

    if len(set(members)) < len(members):
        raise ValueError(f"Duplicate member names. {members}")


@dataclass
class Ledger:
    """
    Stores expense and transfer data and calculates balance between accounts.

    Attributes:
        file_path(Path): Path to file where ledger data is stored.
        members(list[str]): List of account names sharing the expenses.
        entries(list[LedgerEntry]): Registry of ledger entries, both expenses of transfers.
        accounts(dict[str, Account]): Dictionary storing account data.
        settle_transfers(list[Transfer]): List of transfers required to balance the ledger.
        overwrite(bool): If set to True, ledger is reset from the constructor
            and data stored in `file_path` will be overwritten.
        _file_lock(Filelock): File lock used to prevent multiple Ledger instances reading/writing
            to the same file at once.

    """

    file_path: Path
    members: list[str] = field(default_factory=list)
    entries: list[LedgerEntry] = field(default_factory=list)
    accounts: dict[str, Account] = field(default_factory=dict)
    overwrite: bool = False
    track_history: bool = False
    _lock: FileLock = field(init=False)

    @property
    def settle_transfers(self) -> list[Transfer]:
        return self.calculate_balance()

    @property
    def indexed_entries(self) -> list[IndexedLedgerEntry]:
        idx = list(range(len(self.entries)))
        return [(i, e) for i, e in zip(idx, self.entries)]

    def __post_init__(self) -> None:
        self._lock = FileLock(self.file_path.with_name(f".{self.file_path.name}.lock"), timeout=LOCK_TIMEOUT_SECONDS)
        if self.file_path.exists() and not self.overwrite:
            self.load_data_from_file()
            return

        _member_list_sanity_check(self.members)

        if self.track_history:
            self._init_history()

        for name in self.members:
            self.accounts[name] = Account(name=name)

    def _init_history(self) -> None:
        self.history: dict[str, list[Any]] = {}
        self.history["dates"] = []
        self.history["total_expenses"] = []
        for m in self.members:
            self.history[f"account_{m}_paid"] = []

    def _update_history(self, e: LedgerEntry) -> None:
        self.history["dates"].append(e.date)
        self.history["total_expenses"].append(sum(a.spent for a in self.accounts.values()))
        for m in self.members:
            self.history[f"account_{m}_paid"].append(self.accounts[m].paid)

    def load_data_from_file(self) -> None:
        """
        Load ledger data from file.

        Raises:
            ValueError: If number of members is less than 2, or if any name is duplicated.

        """
        with self._lock, open(self.file_path) as f:
            header = next(f)
            self.members = header.strip().split(",")
            _member_list_sanity_check(self.members)
            if self.track_history:
                self._init_history()

            for name in self.members:
                self.accounts[name] = Account(name=name)

            for line in f:
                raw = line.strip().split(",")
                identifier = raw.pop(0)
                date = datetime.datetime.strptime(raw.pop(0), DATE_OUT_FMT).date()
                payer = raw.pop(0)
                quantity = float(raw.pop(0))
                if identifier == "E":
                    concept = raw.pop(0)
                    assignment = {val.split(":")[0]: float(val.split(":")[1]) for val in raw}
                    self.add_expense(
                        Expense(payer=payer, quantity=quantity, concept=concept, assignment=assignment, date=date)
                    )
                elif identifier == "T":
                    recipient = raw[0]
                    self.add_transfer(Transfer(payer=payer, quantity=quantity, recipient=recipient, date=date))
                else:
                    raise ValueError(f"Unknown Entry type while reading file. '{line.strip()}'.")

    def __repr__(self) -> str:
        out = "Member\tTotal Expenses\tTotal Paid\tOwed"
        for name, account in self.accounts.items():
            out += f"\n* {name}\t{account.spent}\t\t{account.paid}\t\t{account.owed}"

        if not self.settle_transfers:
            out += "\n\nExpenses are balanced."
            return out

        out += "\n\nTransfers to settle:"
        for transfer in self.settle_transfers:
            out += f"\n* {transfer}"
        return out

    def save_to_file(self) -> None:
        """Saves ledger data to file."""
        self.entries = sorted(self.entries, key=lambda entry: entry.date)
        with self._lock, open(self.file_path, "w") as f:
            f.write(",".join(self.members) + "\n")
            for entry in self.entries:
                identifier = "E" if isinstance(entry, Expense) else "T"
                f.write(f"{identifier},{entry.to_output()}\n")

    def _filter_by_date(
        self, start_date: datetime.date | None, end_date: datetime.date | None
    ) -> list[IndexedLedgerEntry]:
        filter_date: Callable[[LedgerEntry], bool] = lambda x: True
        if start_date is not None:
            if end_date is not None:
                filter_date = lambda x: x.date >= start_date and x.date <= end_date
            else:
                filter_date = lambda x: x.date >= start_date
        elif end_date is not None:
            filter_date = lambda x: x.date <= end_date

        return [(i, e) for i, e in self.indexed_entries if filter_date(e)]

    def _filter_by_payer(self, entries: list[IndexedLedgerEntry], payer: str) -> list[IndexedLedgerEntry]:
        return [(i, e) for i, e in entries if e.payer == payer]

    def _filter_transfers(self, entries: list[IndexedLedgerEntry], include_transfers: bool) -> list[IndexedLedgerEntry]:
        return [(i, e) for i, e in entries if not isinstance(e, Transfer)] if not include_transfers else entries

    def _filter_by_concept(self, entries: list[IndexedLedgerEntry], concept: str | None) -> list[IndexedLedgerEntry]:
        if concept is not None:
            return [
                (i, e)
                for i, e in entries
                if isinstance(e, Transfer) or (isinstance(e, Expense) and concept in e.concept.lower())
            ]
        return entries

    def search(
        self,
        payer: str,
        concept: str | None = None,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
        include_transfers: bool = False,
    ) -> list[IndexedLedgerEntry]:
        """
        Return a list of ledger filtered by different criteria.

        Args:
            payer: Filter by payer name.
            concept: Filter by concept. The value can be a substring of the concept.
            start_date: Filter entries after that date.
            end_date: Filter entries before that date.
            include_transfers: Include any transfers matching the filtering criteria (except concept).

        Returns:
            Filtered list of ledger entries.

        Raises:
            ValueError: If payer is not a valid member name.

        """
        if payer not in self.members:
            raise ValueError(f"Payer {payer} doesn't exist.")

        filtered_entries = self._filter_by_date(start_date, end_date)
        filtered_entries = self._filter_by_payer(filtered_entries, payer=payer)
        filtered_entries = self._filter_transfers(filtered_entries, include_transfers=include_transfers)
        filtered_entries = self._filter_by_concept(filtered_entries, concept=concept)

        return filtered_entries

    def get_entry(self, index: int) -> LedgerEntry:
        """
        Return ledger entry corresponding to list index.

        Args:
            index: Entry index within list.

        Returns:
            Ledger entry.

        Raises:
            ValueError: If index is out of bounds.

        """
        if index < 0 or index > len(self.entries) - 1:
            raise ValueError("Index out of bounds.")

        return self.entries[index]

    def add_expense(self, expense: Expense) -> None:
        """
        Add expense to the ledger.

        Args:
            expense: Expense entry.

        Raises:
            ValueError: If the expense payer, or any of the names in the expense assignment
            is not in the ledger members.

        """
        if expense.payer not in self.members:
            raise ValueError(f"Expense payer not in members. '{expense.payer}'")
        if any([m not in self.members for m in expense.assignment]):
            raise ValueError(f"Some recipient not in members. {list(expense.assignment.keys())}")

        self.entries.append(expense)

        payer_account = self.accounts[expense.payer]
        payer_account.paid += expense.quantity

        for name, fraction in expense.assignment.items():
            account = self.accounts[name]
            account.spent += expense.quantity * fraction

        if self.track_history:
            self._update_history(expense)

    def add_transfer(self, transfer: Transfer) -> None:
        """
        Add transfer to the ledger.

        Args:
            transfer: Transfer entry.

        Raises:
            ValueError: If the transfer payer or recipient is not in the ledger members.

        """
        if transfer.payer not in self.members:
            raise ValueError(f"Transfer payer not in members. '{transfer.payer}'")
        if transfer.recipient not in self.members:
            raise ValueError(f"Transfer recipient not in members. '{transfer.recipient}'")

        self.entries.append(transfer)

        payer_account = self.accounts[transfer.payer]
        payer_account.paid += transfer.quantity
        recipient_account = self.accounts[transfer.recipient]
        recipient_account.paid -= transfer.quantity

        if self.track_history:
            self._update_history(transfer)

    def delete_entry(self, index: int) -> None:
        """
        Delete ledger entry corresponding to list index.

        Args:
            index: Entry index within list.

        Raises:
            ValueError: If index is out of bounds.

        """
        if index < 0 or index > len(self.entries) - 1:
            raise ValueError("Index out of bounds.")

        self.entries.pop(index)

    def replace_entry(self, index: int, entry: LedgerEntry) -> None:
        """
        Replace ledger entry in a specific list index.

        Args:
            index: Entry index within list.
            entry: Entry to replace.

        Raises:
            ValueError: If index is out of bounds.

        """
        if index < 0 or index > len(self.entries) - 1:
            raise ValueError("Index out of bounds.")

        self.entries[index] = entry

    def calculate_balance(self) -> list[Transfer]:
        """
        Calculate a set of transfers between member that will balance the ledger.

        Transfers are calculated by sorting the ledger accounts by amount owed in descending order
        and settling accounts starting from the edges (most owed/indebted)and moving towards the center
        (least owed/indebted).

        Returns:
            List of transfers that will balance the ledger.

        """
        sorted_accounts: list[Account] = sorted(self.accounts.values(), key=lambda a: a.owed, reverse=True)
        logger.debug(f"{dict({a.name: a.owed for a in sorted_accounts})}")

        pointer_indebted = 0
        pointer_receiver = len(sorted_accounts) - 1

        indebted_account = sorted_accounts[pointer_indebted]
        receiver_account = sorted_accounts[pointer_receiver]
        remaining_owed = indebted_account.owed
        remaining_to_settle = abs(receiver_account.owed)

        settle_transfers = []

        logger.debug(f"rem owed: {remaining_owed} / rem settle {remaining_to_settle}")

        while pointer_indebted < pointer_receiver:
            # Check if we have moved through all the over indebted accounts
            if indebted_account.owed <= 0.0:
                break

            if remaining_owed <= remaining_to_settle:
                transfer = Transfer(
                    payer=indebted_account.name, quantity=remaining_owed, recipient=receiver_account.name
                )
                settle_transfers.append(transfer)

                remaining_to_settle -= remaining_owed

                pointer_indebted += 1
                indebted_account = sorted_accounts[pointer_indebted]
                remaining_owed = indebted_account.owed

                if remaining_to_settle == 0.0:
                    pointer_receiver -= 1
                    receiver_account = sorted_accounts[pointer_receiver]
                    remaining_to_settle = abs(receiver_account.owed)

            else:
                transfer = Transfer(
                    payer=indebted_account.name, quantity=remaining_to_settle, recipient=receiver_account.name
                )
                settle_transfers.append(transfer)

                remaining_owed -= remaining_to_settle

                pointer_receiver -= 1
                receiver_account = sorted_accounts[pointer_receiver]
                remaining_to_settle = abs(receiver_account.owed)

        return settle_transfers
