import logging
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Self

logger = logging.getLogger(__name__)


@dataclass
class Account:
    name: str
    spent: float = 0.0
    paid: float = 0.0

    @property
    def owed(self) -> float:
        return self.spent - self.paid


@dataclass
class Expense:
    payer: str
    quantity: float
    assignment: dict[str, float]

    def __post_init__(self) -> None:
        if sum(list(self.assignment.values())) == 1.0:
            return

        logger.info("Assignment weights doesn't add up to 1, normalising.")
        total = sum(list(self.assignment.values()))
        for name, value in self.assignment.items():
            self.assignment[name] = value / total


@dataclass
class Transfer:
    payer: str
    quantity: float
    recipient: str

    def __post_init__(self) -> None:
        if self.payer == self.recipient:
            raise ValueError("Payer and recipient must be different.")

    def __repr__(self) -> str:
        return f"Transfer '{self.payer}' -> '{self.recipient}': {self.quantity}."


def _load_ledger_from_file(file_path: Path) -> tuple[list[str], list[Expense]]:
    with open(file_path) as f:
        header = next(f)
        members = header.strip().split(",")
        expenses = []
        for line in f:
            raw = line.strip().split(",")
            payer = raw.pop(0)
            quantity = float(raw.pop(0))
            assignment = {val.split(":")[0]: float(val.split(":")[1]) for val in raw}
            expenses.append(Expense(payer=payer, quantity=quantity, assignment=assignment))
    return members, expenses


@dataclass
class Ledger:
    members: list[str]
    expenses: list[Expense] = field(default_factory=list)
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

    @classmethod
    def from_file(cls, file_path: Path) -> Self:
        members, expenses = _load_ledger_from_file(file_path)
        ledger = cls(members=members)
        for x in expenses:
            ledger.add_expense(x)
        return ledger

    def __repr__(self) -> str:
        out = "Member\tTotal Expenses\tTotal Paid\tOwed"
        for name, account in self.accounts.items():
            out += f"\n* {name}\t{account.spent}\t\t{account.paid}\t\t{account.owed}"
        out += "\n\nTransfers to settle:"
        for transfer in self.settle_transfers:
            out += f"\n* {transfer}"
        return out

    def save_ledger_to_file(self, file_path: Path) -> None:
        with open(file_path, "w") as f:
            f.write(",".join(self.members) + "\n")
            for exp in self.expenses:
                assignment_str = [f"{n}:{d}" for n, d in exp.assignment.items()]
                f.write(",".join([exp.payer, str(exp.quantity)] + assignment_str) + "\n")

    def add_expense(self, expense: Expense) -> None:
        if expense.payer not in self.members:
            raise ValueError(f"Expense payer not in members. {expense.payer}")
        if any([m not in self.members for m in expense.assignment]):
            raise ValueError(f"Some recipient not in members.{list(expense.assignment.keys())}")

        self.expenses.append(expense)

        payer_account = self.accounts[expense.payer]
        payer_account.paid += expense.quantity

        for name, fraction in expense.assignment.items():
            account = self.accounts[name]
            account.spent += expense.quantity * fraction

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

                logger.debug(f"a transfer {transfer}")
                logger.debug(f"a rem owed: {remaining_owed} / rem settle {remaining_to_settle}")

            else:
                transfer_quantity = remaining_to_settle
                transfer = Transfer(
                    payer=indebted_account.name, quantity=transfer_quantity, recipient=receiver_account.name
                )
                settle_transfers.append(transfer)

                remaining_owed -= transfer_quantity
                pointer_receiver -= 1

                receiver_account = sorted_accounts[pointer_receiver]
                remaining_to_settle = abs(receiver_account.owed)

                logger.debug(f"b transfer {transfer}")
                logger.debug(f"b rem owed: {remaining_owed} / rem settle {remaining_to_settle}")

        return settle_transfers
