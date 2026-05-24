import datetime
import logging
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Protocol
from typing import Self

logger = logging.getLogger(__name__)

DATE_OUT_FMT = "%d/%m/%Y"


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


def _load_ledger_from_file(file_path: Path) -> tuple[list[str], list[LedgerEntry]]:
    with open(file_path) as f:
        header = next(f)
        members = header.strip().split(",")
        entries: list[LedgerEntry] = []
        for line in f:
            raw = line.strip().split(",")
            identifier = raw.pop(0)
            date = datetime.datetime.strptime(raw.pop(0), DATE_OUT_FMT).date()
            payer = raw.pop(0)
            quantity = float(raw.pop(0))
            if identifier == "E":
                concept = raw.pop(0)
                assignment = {val.split(":")[0]: float(val.split(":")[1]) for val in raw}
                entries.append(
                    Expense(payer=payer, quantity=quantity, concept=concept, assignment=assignment, date=date)
                )
            else:
                recipient = raw[0]
                entries.append(Transfer(payer=payer, quantity=quantity, recipient=recipient, date=date))
    return members, entries


@dataclass
class Ledger:
    members: list[str]
    entries: list[LedgerEntry] = field(init=False)
    accounts: dict[str, Account] = field(init=False)

    @property
    def settle_transfers(self) -> list[Transfer]:
        return self.calculate_balance()

    def __post_init__(self) -> None:
        if len(self.members) <= 1:
            raise ValueError("Include at least two members.")

        if len(set(self.members)) < len(self.members):
            raise ValueError("Duplicate member names.")

        self.accounts = {}
        for name in self.members:
            self.accounts[name] = Account(name=name)

        self.entries = []

    @classmethod
    def from_file(cls, file_path: Path) -> Self:
        members, entries = _load_ledger_from_file(file_path)
        ledger = cls(members=members)

        for entry in entries:
            if isinstance(entry, Expense):
                ledger.add_expense(entry)
            elif isinstance(entry, Transfer):
                ledger.add_transfer(entry)
            else:
                raise ValueError(f"Unknown Entry type (should never happen). {entry}.")

        return ledger

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

    def save_ledger_to_file(self, file_path: Path) -> None:
        self.entries = sorted(self.entries, key=lambda entry: entry.date)
        with open(file_path, "w") as f:
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
