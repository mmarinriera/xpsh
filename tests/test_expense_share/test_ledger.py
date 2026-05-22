from datetime import date
from pathlib import Path

import pytest

from expense_share.ledger import Account
from expense_share.ledger import Expense
from expense_share.ledger import Ledger
from expense_share.ledger import Transfer

GENERIC_DATE = date(2000, 1, 1)


def test_account() -> None:
    account = Account(name="A", spent=10.0, paid=20.0)
    assert account.owed == -10.0


def test_expense(subtests: pytest.Subtests) -> None:
    expense_0 = Expense(payer="A", quantity=10.0, assignment={"A": 0.5, "B": 0.5}, date=GENERIC_DATE)
    expense_1 = Expense(payer="A", quantity=20.0, assignment={"A": 3, "B": 1}, date=GENERIC_DATE)

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
        str(Expense(payer="A", quantity=10.0, assignment={"A": 0.5, "B": 0.5}, date=GENERIC_DATE)),
        str(Expense(payer="B", quantity=20.0, assignment={"A": 0.5, "B": 0.5}, date=GENERIC_DATE)),
    ]

    ledger = Ledger.from_file(example_file_path)
    with subtests.test("Test ledger from file: members"):
        assert ledger.members == TARGET_MEMBERS
    with subtests.test("Test ledger from file: accounts"):
        assert ledger.accounts == TARGET_ACCOUNTS
    with subtests.test("Test ledger from file: expenses"):
        assert [str(exp) for exp in ledger.expenses] == TARGET_EXPENSES


def test_ledger_save_to_file(tmp_path: Path) -> None:
    TARGET_FILE_CONTENT = """A,B
01/01/2000,A,10.0,A:0.5,B:0.5
01/01/2000,B,20.0,A:0.5,B:0.5
"""
    ledger = Ledger(members=["A", "B"])
    ledger.add_expense(Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, date=GENERIC_DATE))
    ledger.add_expense(Expense(payer="B", quantity=20.0, assignment={"A": 1, "B": 1}, date=GENERIC_DATE))

    out_path = tmp_path / "out.txt"
    ledger.save_ledger_to_file(out_path)
    with open(out_path) as f:
        out_content = f.read()

    assert out_content == TARGET_FILE_CONTENT


def test_ledger_save_to_file_unsorted(tmp_path: Path) -> None:
    TARGET_FILE_CONTENT = """A,B
01/01/2000,A,10.0,A:0.5,B:0.5
02/01/2000,B,20.0,A:0.5,B:0.5
03/01/2000,B,30.0,A:0.5,B:0.5
"""
    ledger = Ledger(members=["A", "B"])
    ledger.add_expense(Expense(payer="B", quantity=30.0, assignment={"A": 1, "B": 1}, date=date(2000, 1, 3)))
    ledger.add_expense(Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, date=date(2000, 1, 1)))
    ledger.add_expense(Expense(payer="B", quantity=20.0, assignment={"A": 1, "B": 1}, date=date(2000, 1, 2)))

    out_path = tmp_path / "out.txt"
    ledger.save_ledger_to_file(out_path)
    with open(out_path) as f:
        out_content = f.read()

    assert out_content == TARGET_FILE_CONTENT


def test_representation(subtests: pytest.Subtests) -> None:
    TARGET_REPR_NO_BALANCED = """Member\tTotal Expenses\tTotal Paid\tOwed
* A\t15.0\t\t10.0\t\t5.0
* B\t15.0\t\t20.0\t\t-5.0

Transfers to settle:
* Transfer 'A' -> 'B': 5.0."""

    TARGET_REPR_BALANCED = """Member\tTotal Expenses\tTotal Paid\tOwed
* A\t20.0\t\t20.0\t\t0.0
* B\t20.0\t\t20.0\t\t0.0

Expenses are balanced."""

    ledger_0 = Ledger(members=["A", "B"])
    ledger_0.add_expense(Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, date=GENERIC_DATE))
    ledger_0.add_expense(Expense(payer="B", quantity=20.0, assignment={"A": 1, "B": 1}, date=GENERIC_DATE))
    with subtests.test("Test ledger repr non-balanced."):
        assert str(ledger_0) == TARGET_REPR_NO_BALANCED

    ledger_0.add_expense(Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, date=GENERIC_DATE))
    with subtests.test("Test ledger repr balanced."):
        assert str(ledger_0) == TARGET_REPR_BALANCED


def test_add_expense(subtests: pytest.Subtests) -> None:
    ledger = Ledger(members=["A", "B"])
    ledger.add_expense(Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, date=GENERIC_DATE))
    with subtests.test("Test add one expense."):
        assert ledger.accounts["A"].paid == 10.0
        assert ledger.accounts["A"].spent == 5.0
        assert ledger.accounts["A"].owed == -5.0
        assert ledger.accounts["B"].paid == 0.0
        assert ledger.accounts["B"].spent == 5.0
        assert ledger.accounts["B"].owed == 5.0

    ledger.add_expense(Expense(payer="B", quantity=12.0, assignment={"A": 2, "B": 1}, date=GENERIC_DATE))
    with subtests.test("Test add another expense."):
        assert ledger.accounts["A"].paid == 10.0
        assert ledger.accounts["A"].spent == 13.0
        assert ledger.accounts["A"].owed == 3.0
        assert ledger.accounts["B"].paid == 12.0
        assert ledger.accounts["B"].spent == 9.0
        assert ledger.accounts["B"].owed == -3.0

    ledger.add_expense(Expense(payer="B", quantity=5.0, assignment={"A": 1}, date=GENERIC_DATE))
    with subtests.test("Test add expense with partial assignment."):
        assert ledger.accounts["A"].paid == 10.0
        assert ledger.accounts["A"].spent == 18.0
        assert ledger.accounts["A"].owed == 8.0
        assert ledger.accounts["B"].paid == 17.0
        assert ledger.accounts["B"].spent == 9.0
        assert ledger.accounts["B"].owed == -8.0

    with subtests.test("Add expense with unknown payer."):
        with pytest.raises(ValueError, match="Expense payer not in members. 'C'"):
            ledger.add_expense(Expense(payer="C", quantity=5.0, assignment={"A": 1, "B": 1}, date=GENERIC_DATE))

    with subtests.test("Add expense with unknown assignee."):
        with pytest.raises(ValueError, match=r"Some recipient not in members. \['A', 'B', 'C'\]"):
            ledger.add_expense(Expense(payer="A", quantity=5.0, assignment={"A": 1, "B": 1, "C": 1}, date=GENERIC_DATE))


def test_calculate_balance(subtests: pytest.Subtests) -> None:
    ledger_0 = Ledger(members=["A", "B"])
    ledger_0.add_expense(Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, date=GENERIC_DATE))
    ledger_0.add_expense(Expense(payer="B", quantity=20.0, assignment={"A": 1, "B": 1}, date=GENERIC_DATE))
    TARGET_TRANSFERS_0 = [Transfer("A", 5.0, "B")]

    with subtests.test("Calculate balance with two members"):
        assert ledger_0.calculate_balance() == TARGET_TRANSFERS_0

    ledger_1 = Ledger(members=["A", "B", "C", "D"])
    ledger_1.add_expense(Expense(payer="A", quantity=12.0, assignment={"A": 1, "C": 1, "D": 1}, date=GENERIC_DATE))
    ledger_1.add_expense(Expense(payer="B", quantity=24.0, assignment={"A": 1, "B": 1, "D": 1}, date=GENERIC_DATE))
    TARGET_TRANSFERS_1 = [
        Transfer("C", 4.0, "B"),
        Transfer("D", 12.0, "B"),
    ]

    with subtests.test("Calculate balance with 4 members and 3 transfers"):
        assert sorted(ledger_1.calculate_balance(), key=lambda t: t.quantity) == TARGET_TRANSFERS_1

    ledger_2 = Ledger(members=["A", "B", "C", "D"])
    ledger_2.add_expense(
        Expense(payer="A", quantity=12.0, assignment={"A": 1, "B": 1, "C": 1, "D": 1}, date=GENERIC_DATE)
    )
    ledger_2.add_expense(Expense(payer="B", quantity=24.0, assignment={"A": 1, "B": 1, "D": 1}, date=GENERIC_DATE))
    TARGET_TRANSFERS_2 = [
        Transfer("C", 1.0, "A"),
        Transfer("C", 2.0, "B"),
        Transfer("D", 11.0, "B"),
    ]

    with subtests.test("Calculate balance with 4 members and 3 transfers"):
        assert sorted(ledger_2.calculate_balance(), key=lambda t: t.quantity) == TARGET_TRANSFERS_2
