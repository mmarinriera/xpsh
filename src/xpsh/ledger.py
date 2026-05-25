import datetime
import logging
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Protocol

from filelock import FileLock

logger = logging.getLogger(__name__)

DATE_OUT_FMT = "%d/%m/%Y"
LOCK_TIMEOUT_SECONDS = 10


@dataclass
class Account:
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
        raise NotImplementedError


@dataclass
class Expense:
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
        assignment_out = [f"{n}:{d}" for n, d in self.assignment.items()]
        concept_out = self.concept.replace(",", "")
        return ",".join(
            [self.date.strftime(DATE_OUT_FMT), self.payer, str(self.quantity), concept_out] + assignment_out
        )


@dataclass
class Transfer:
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
        return ",".join([self.date.strftime(DATE_OUT_FMT), self.payer, str(self.quantity), self.recipient])


def _member_list_sanity_check(members: list[str]) -> None:
    if len(members) <= 1:
        raise ValueError(f"Include at least two members. {members}")

    if len(set(members)) < len(members):
        raise ValueError(f"Duplicate member names. {members}")


@dataclass
class Ledger:
    file_path: Path
    members: list[str] = field(default_factory=list)
    entries: list[LedgerEntry] = field(default_factory=list)
    accounts: dict[str, Account] = field(default_factory=dict)
    _lock: FileLock = field(init=False)

    @property
    def settle_transfers(self) -> list[Transfer]:
        return self.calculate_balance()

    def __post_init__(self) -> None:
        self._lock = FileLock(self.file_path.with_name(f".{self.file_path.name}.lock"), timeout=LOCK_TIMEOUT_SECONDS)
        if self.file_path.exists():
            self.load_data_from_file()
            return

        _member_list_sanity_check(self.members)

        for name in self.members:
            self.accounts[name] = Account(name=name)

    def load_data_from_file(self) -> None:
        with self._lock, open(self.file_path) as f:
            header = next(f)
            self.members = header.strip().split(",")
            _member_list_sanity_check(self.members)
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
        self.entries = sorted(self.entries, key=lambda entry: entry.date)
        with self._lock, open(self.file_path, "w") as f:
            f.write(",".join(self.members) + "\n")
            for entry in self.entries:
                identifier = "E" if isinstance(entry, Expense) else "T"
                f.write(f"{identifier},{entry.to_output()}\n")

    def add_expense(self, expense: Expense) -> None:
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

    def add_transfer(self, transfer: Transfer) -> None:
        if transfer.payer not in self.members:
            raise ValueError(f"Transfer payer not in members. '{transfer.payer}'")
        if transfer.recipient not in self.members:
            raise ValueError(f"Transfer recipient not in members. '{transfer.recipient}'")

        self.entries.append(transfer)

        payer_account = self.accounts[transfer.payer]
        payer_account.paid += transfer.quantity
        recipient_account = self.accounts[transfer.recipient]
        recipient_account.paid -= transfer.quantity

    def calculate_balance(self) -> list[Transfer]:
        """
        Calculate who owes money to who.

        Sorting the accounts by total amount owed, then assigning transfers between accounts prioritising largest transfers.
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
            logger.info(f"it p0 {sorted_accounts[pointer_indebted].name}, p1 {sorted_accounts[pointer_receiver].name}")
            # Check if we have moved through all the over indebted accounts
            if indebted_account.owed <= 0.0:
                break

            if remaining_owed <= remaining_to_settle:
                transfer = Transfer(
                    payer=indebted_account.name, quantity=remaining_owed, recipient=receiver_account.name
                )
                settle_transfers.append(transfer)

                logger.info(f"transfer {transfer}")

                remaining_to_settle -= remaining_owed

                pointer_indebted += 1
                indebted_account = sorted_accounts[pointer_indebted]
                remaining_owed = indebted_account.owed

                if remaining_to_settle == 0.0:
                    pointer_receiver -= 1
                    receiver_account = sorted_accounts[pointer_receiver]
                    remaining_to_settle = abs(receiver_account.owed)
                logger.info(
                    f"next p0 {sorted_accounts[pointer_indebted].name}, next p1 {sorted_accounts[pointer_receiver].name} rset {remaining_to_settle}, rowed {remaining_owed}"
                )

            else:
                transfer = Transfer(
                    payer=indebted_account.name, quantity=remaining_to_settle, recipient=receiver_account.name
                )
                settle_transfers.append(transfer)

                logger.info(f"transfer {transfer}")

                remaining_owed -= remaining_to_settle

                pointer_receiver -= 1
                receiver_account = sorted_accounts[pointer_receiver]
                remaining_to_settle = abs(receiver_account.owed)

                if remaining_owed == 0.0:
                    pointer_indebted += 1
                    indebted_account = sorted_accounts[pointer_indebted]
                    remaining_owed = indebted_account.owed

                logger.info(
                    f"next p0 {sorted_accounts[pointer_indebted].name}, next p1 {sorted_accounts[pointer_receiver].name} rset {remaining_to_settle}, rowed {remaining_owed}"
                )

        logger.info(f"settle: {settle_transfers}")

        return settle_transfers
