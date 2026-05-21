from pathlib import Path

import pytest

from expense_share.ledger import Account
from expense_share.ledger import Expense
from expense_share.ledger import Ledger
from expense_share.ledger import Transfer


def get_resource(file_name: str) -> Path:
    base_dir = Path.cwd()
    return base_dir / "tests" / "resources" / file_name


@pytest.fixture
def example_file_path() -> Path:
    return get_resource("example.txt")


def test_account() -> None:
    account = Account(name="A", spent=10.0, paid=20.0)
    assert account.owed == -10.0


def test_expense(subtests: pytest.Subtests) -> None:
    expense_0 = Expense(payer="A", quantity=10.0, assignment={"A": 0.5, "B": 0.5})
    expense_1 = Expense(payer="A", quantity=20.0, assignment={"A": 3, "B": 1})

    with subtests.test("Test expense assignments with fractions"):
        assert expense_0.assignment == {"A": 0.5, "B": 0.5}

    with subtests.test("Test expense assignments with integer parts"):
        assert expense_1.assignment == {"A": 0.75, "B": 0.25}


def test_transfer(subtests: pytest.Subtests) -> None:
    transfer_0 = Transfer(payer="A", quantity=10.0, recipient="B")
    TARGET_REPR = "Transfer 'A' -> 'B': 10.0."

    with subtests.test("Test transfer representation"):
        assert str(transfer_0) == TARGET_REPR

    with subtests.test("Test transfer payer is same as recipient"):
        with pytest.raises(ValueError, match="Payer and recipient must be different."):
            _ = Transfer(payer="A", quantity=20.0, recipient="A")


def test_ledger_init(subtests: pytest.Subtests) -> None:
    ledger_0 = Ledger(members=["A", "B", "C"])
    with subtests.test("Test ledger accounts attribute"):
        assert list(ledger_0.accounts.keys()) == ledger_0.members
        assert all([isinstance(a, Account) for a in ledger_0.accounts.values()])

    with subtests.test("Test ledger with members < 2"):
        with pytest.raises(ValueError, match="Include at least two members."):
            _ = Ledger(members=["A"])

    with subtests.test("Test ledger duplicate members"), pytest.raises(ValueError, match="Duplicate member names."):
        _ = Ledger(members=["A", "A"])


def test_ledger_load_from_file(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_MEMBERS = ["A", "B"]
    TARGET_ACCOUNTS = {
        "A": Account(name="A", spent=15.0, paid=10.0),
        "B": Account(name="B", spent=15.0, paid=20.0),
    }
    TARGET_EXPENSES = [
        Expense(payer="A", quantity=10.0, assignment={"A": 0.5, "B": 0.5}),
        Expense(payer="B", quantity=20.0, assignment={"A": 0.5, "B": 0.5}),
    ]

    ledger = Ledger.from_file(example_file_path)
    with subtests.test("Test ledger from file: members"):
        assert ledger.members == TARGET_MEMBERS
    with subtests.test("Test ledger from file: accounts"):
        assert ledger.accounts == TARGET_ACCOUNTS
    with subtests.test("Test ledger from file: expenses"):
        assert ledger.expenses == TARGET_EXPENSES
