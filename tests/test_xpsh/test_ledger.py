from datetime import date
from pathlib import Path

import pytest

from xpsh import Account
from xpsh import Expense
from xpsh import Ledger
from xpsh import Transfer
from xpsh.ledger import DATE_OUT_FMT

GENERIC_DATE = date(2000, 1, 1)


def test_account() -> None:
    account = Account(name="A", spent=10.0, paid=20.0)
    assert account.owed == -10.0


def test_expense(subtests: pytest.Subtests) -> None:
    expense_0 = Expense(payer="A", quantity=10.0, assignment={"A": 0.5, "B": 0.5}, concept="Stuff", date=GENERIC_DATE)
    TARGET_OUTPUT = "01/01/2000,A,10.0,Stuff,A:0.5,B:0.5"
    expense_1 = Expense(payer="A", quantity=20.0, assignment={"A": 3, "B": 1}, concept="More stuff", date=GENERIC_DATE)

    with subtests.test("Test expense assignments with fractions"):
        assert expense_0.assignment == {"A": 0.5, "B": 0.5}

    with subtests.test("Test expense assignments with integer parts"):
        assert expense_1.assignment == {"A": 0.75, "B": 0.25}

    with subtests.test("Test expense output."):
        assert expense_0.to_output() == TARGET_OUTPUT


def test_transfer(subtests: pytest.Subtests) -> None:
    transfer_0 = Transfer(payer="A", quantity=10.0, recipient="B", date=GENERIC_DATE)
    TARGET_REPR = "Transfer 'A' -> 'B': 10.0."
    TARGET_OUTPUT_0 = "01/01/2000,A,10.0,B"
    transfer_1 = Transfer(payer="A", quantity=10.0, recipient="B")
    TARGET_OUTPUT_1 = f"{date.today().strftime(DATE_OUT_FMT)},A,10.0,B"

    with subtests.test("Test transfer representation"):
        assert str(transfer_0) == TARGET_REPR

    with subtests.test("Test transfer payer is same as recipient"):
        with pytest.raises(ValueError, match="Payer and recipient must be different."):
            _ = Transfer(payer="A", quantity=20.0, recipient="A")

    with subtests.test("Test transfer output."):
        assert transfer_0.to_output() == TARGET_OUTPUT_0

    with subtests.test("Test transfer output default date."):
        assert transfer_1.to_output() == TARGET_OUTPUT_1


def test_ledger_init(subtests: pytest.Subtests, tmp_path: Path) -> None:
    out_path = tmp_path / "out.txt"
    ledger_0 = Ledger(file_path=out_path, members=["A", "B", "C"])
    with subtests.test("Test ledger accounts attribute"):
        assert list(ledger_0.accounts.keys()) == ledger_0.members
        assert all([isinstance(a, Account) for a in ledger_0.accounts.values()])

    with subtests.test("Test ledger with members < 2"):
        with pytest.raises(ValueError, match=r"Include at least two members. \['A'\]"):
            _ = Ledger(file_path=out_path, members=["A"])

    with (
        subtests.test("Test ledger duplicate members"),
        pytest.raises(ValueError, match=r"Duplicate member names. \['A', 'A'\]"),
    ):
        _ = Ledger(file_path=out_path, members=["A", "A"])


def test_ledger_overwrite(tmp_path: Path, example_file_path: Path, subtests: pytest.Subtests) -> None:
    out_path_new = tmp_path / "out.txt"
    TARGET_MEMBERS = ["C", "D"]
    ledger_0 = Ledger(file_path=out_path_new, members=["C", "D"], overwrite=True)
    with subtests.test("Test ledger init overwrite: members"):
        assert ledger_0.members == TARGET_MEMBERS

    ledger_1 = Ledger(file_path=example_file_path, members=["C", "D"], overwrite=True)
    with subtests.test("Test ledger init overwrite: members"):
        assert ledger_1.members == TARGET_MEMBERS


def test_ledger_load_from_file(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_MEMBERS = ["A", "B"]
    TARGET_ACCOUNTS = {
        "A": Account(name="A", spent=15.0, paid=10.0),
        "B": Account(name="B", spent=15.0, paid=20.0),
    }
    TARGET_EXPENSES = [
        str(Expense(payer="A", quantity=10.0, assignment={"A": 0.5, "B": 0.5}, concept="Stuff", date=GENERIC_DATE)),
        str(
            Expense(payer="B", quantity=20.0, assignment={"A": 0.5, "B": 0.5}, concept="More stuff", date=GENERIC_DATE)
        ),
    ]

    ledger = Ledger(file_path=example_file_path)
    with subtests.test("Test ledger from file: members"):
        assert ledger.members == TARGET_MEMBERS
    with subtests.test("Test ledger from file: accounts"):
        assert ledger.accounts == TARGET_ACCOUNTS
    with subtests.test("Test ledger from file: expenses"):
        assert [str(entry) for entry in ledger.entries] == TARGET_EXPENSES

    ledger_with_params = Ledger(file_path=example_file_path, members=["C", "D"])
    with subtests.test("Test ledger from file superseeds constructor params"):
        assert ledger_with_params.members == TARGET_MEMBERS


def test_ledger_load_from_faulty_file(tmp_path: Path, subtests: pytest.Subtests) -> None:
    out_path_0 = tmp_path / "faulty_0.txt"
    with open(out_path_0, "w") as f:
        f.write("CD\nE,CD,10.0\n")
    with subtests.test("Test ledger load file with single member"):
        with pytest.raises(ValueError, match=r"Include at least two members. \['CD'\]"):
            _ = Ledger(out_path_0)

    out_path_1 = tmp_path / "faulty_1.txt"
    with open(out_path_1, "w") as f:
        f.write("C,C,D\nE,C,10.0\n")
    with subtests.test("Test ledger load file with duplicate member"):
        with pytest.raises(ValueError, match=r"Duplicate member names. \['C', 'C', 'D'\]"):
            _ = Ledger(out_path_1)

    out_path_2 = tmp_path / "faulty_2.txt"
    with open(out_path_2, "w") as f:
        f.write("C,D\nX,01/01/2000,C,10.0\n")
    with subtests.test("Test ledger load file with faulty entry"):
        with pytest.raises(ValueError, match="Unknown Entry type while reading file. 'X,01/01/2000,C,10.0'"):
            _ = Ledger(out_path_2)


def test_ledger_save_to_file(tmp_path: Path) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""
    out_path = tmp_path / "out.txt"
    ledger = Ledger(file_path=out_path, members=["A", "B"])
    ledger.add_expense(
        Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Stuff", date=GENERIC_DATE)
    )
    ledger.add_expense(
        Expense(payer="B", quantity=20.0, assignment={"A": 1, "B": 1}, concept="More stuff", date=GENERIC_DATE)
    )

    ledger.save_to_file()
    with open(out_path) as f:
        out_content = f.read()

    assert out_content == TARGET_FILE_CONTENT


def test_ledger_save_to_file_unsorted(tmp_path: Path) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,02/01/2000,B,20.0,More stuff,A:0.5,B:0.5
E,03/01/2000,B,30.0,Even more stuff,A:0.5,B:0.5
"""
    out_path = tmp_path / "out.txt"
    ledger = Ledger(file_path=out_path, members=["A", "B"])
    ledger.add_expense(
        Expense(payer="B", quantity=30.0, assignment={"A": 1, "B": 1}, concept="Even more stuff", date=date(2000, 1, 3))
    )
    ledger.add_expense(
        Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Stuff", date=date(2000, 1, 1))
    )
    ledger.add_expense(
        Expense(payer="B", quantity=20.0, assignment={"A": 1, "B": 1}, concept="More stuff", date=date(2000, 1, 2))
    )

    ledger.save_to_file()
    with open(out_path) as f:
        out_content = f.read()

    assert out_content == TARGET_FILE_CONTENT


def test_representation(tmp_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_REPR_NO_BALANCED = """Member\tTotal Expenses\tTotal Paid\tOwed
* A\t15.0\t\t10.0\t\t5.0
* B\t15.0\t\t20.0\t\t-5.0

Transfers to settle:
* Transfer 'A' -> 'B': 5.0."""

    TARGET_REPR_BALANCED = """Member\tTotal Expenses\tTotal Paid\tOwed
* A\t20.0\t\t20.0\t\t0.0
* B\t20.0\t\t20.0\t\t0.0

Expenses are balanced."""

    out_path = tmp_path / "out.txt"
    ledger_0 = Ledger(file_path=out_path, members=["A", "B"])
    ledger_0.add_expense(
        Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Stuff", date=GENERIC_DATE)
    )
    ledger_0.add_expense(
        Expense(payer="B", quantity=20.0, assignment={"A": 1, "B": 1}, concept="Mores stuff", date=GENERIC_DATE)
    )
    with subtests.test("Test ledger repr non-balanced."):
        assert str(ledger_0) == TARGET_REPR_NO_BALANCED

    ledger_0.add_expense(
        Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Even more stuff", date=GENERIC_DATE)
    )
    with subtests.test("Test ledger repr balanced."):
        assert str(ledger_0) == TARGET_REPR_BALANCED


def test_search(tmp_path: Path, subtests: pytest.Subtests) -> None:
    out_path = tmp_path / "out.txt"
    ledger = Ledger(file_path=out_path, members=["A", "B"])
    exp_0 = Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Stuff", date=date(2000, 1, 1))
    exp_1 = Expense(payer="B", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Stuff", date=date(2000, 1, 2))
    exp_2 = Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Other", date=date(2000, 1, 3))
    exp_3 = Expense(payer="B", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Else", date=date(2000, 1, 4))
    trans_0 = Transfer(payer="A", quantity=10.0, recipient="B", date=date(2000, 1, 2))

    ledger.add_expense(exp_0)
    ledger.add_expense(exp_1)
    ledger.add_expense(exp_2)
    ledger.add_expense(exp_3)
    ledger.add_transfer(trans_0)

    with subtests.test("Test ledger search by payer."):
        assert ledger.search(payer="A") == [(0, exp_0), (2, exp_2)]

    with subtests.test("Test ledger search by payer, filtered by date."):
        assert ledger.search(payer="A", start_date=date(2000, 1, 2), end_date=date(2000, 1, 4)) == [(2, exp_2)]

    with subtests.test("Test ledger search by payer, filtered by concept."):
        assert ledger.search(payer="A", concept="stuff") == [(0, exp_0)]

    with subtests.test("Test ledger search by payer, including transfers."):
        assert ledger.search(payer="A", include_transfers=True) == [(0, exp_0), (2, exp_2), (4, trans_0)]

    with subtests.test("Test ledger search by payer, no hits."):
        assert ledger.search(payer="A", concept="Spam") == []

    with subtests.test("Test ledger search by payer, no hits."):
        with pytest.raises(ValueError, match="Payer C doesn't exist."):
            ledger.search(payer="C")


def test_add_expense(tmp_path: Path, subtests: pytest.Subtests) -> None:
    out_path = tmp_path / "out.txt"
    ledger = Ledger(file_path=out_path, members=["A", "B"])
    ledger.add_expense(
        Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Stuff", date=GENERIC_DATE)
    )
    with subtests.test("Test add one expense."):
        assert ledger.accounts["A"].paid == 10.0
        assert ledger.accounts["A"].spent == 5.0
        assert ledger.accounts["A"].owed == -5.0
        assert ledger.accounts["B"].paid == 0.0
        assert ledger.accounts["B"].spent == 5.0
        assert ledger.accounts["B"].owed == 5.0

    ledger.add_expense(
        Expense(payer="B", quantity=12.0, assignment={"A": 2, "B": 1}, concept="More stuff", date=GENERIC_DATE)
    )
    with subtests.test("Test add another expense."):
        assert ledger.accounts["A"].paid == 10.0
        assert ledger.accounts["A"].spent == 13.0
        assert ledger.accounts["A"].owed == 3.0
        assert ledger.accounts["B"].paid == 12.0
        assert ledger.accounts["B"].spent == 9.0
        assert ledger.accounts["B"].owed == -3.0

    ledger.add_expense(
        Expense(payer="B", quantity=5.0, assignment={"A": 1}, concept="Even more stuff", date=GENERIC_DATE)
    )
    with subtests.test("Test add expense with partial assignment."):
        assert ledger.accounts["A"].paid == 10.0
        assert ledger.accounts["A"].spent == 18.0
        assert ledger.accounts["A"].owed == 8.0
        assert ledger.accounts["B"].paid == 17.0
        assert ledger.accounts["B"].spent == 9.0
        assert ledger.accounts["B"].owed == -8.0

    with subtests.test("Add expense with unknown payer."):
        with pytest.raises(ValueError, match="Expense payer not in members. 'C'"):
            ledger.add_expense(
                Expense(payer="C", quantity=5.0, assignment={"A": 1, "B": 1}, concept="Stuff", date=GENERIC_DATE)
            )

    with subtests.test("Add expense with unknown assignee."):
        with pytest.raises(ValueError, match=r"Some recipient not in members. \['A', 'B', 'C'\]"):
            ledger.add_expense(
                Expense(
                    payer="A", quantity=5.0, assignment={"A": 1, "B": 1, "C": 1}, concept="Stuff", date=GENERIC_DATE
                )
            )


def test_add_reimbursement(tmp_path: Path, subtests: pytest.Subtests) -> None:
    out_path = tmp_path / "out.txt"
    ledger = Ledger(file_path=out_path, members=["A", "B"])
    acc_a = ledger.accounts["A"]
    acc_b = ledger.accounts["B"]
    ledger.add_expense(
        Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Stuff", date=GENERIC_DATE)
    )
    ledger.add_expense(
        Expense(payer="A", quantity=-10.0, assignment={"A": 1, "B": 1}, concept="Reimbursement", date=GENERIC_DATE)
    )
    with subtests.test("Test account balanced with reimbursement."):
        assert acc_a.paid == 0.0
        assert acc_a.spent == 0.0
        assert acc_a.owed == 0.0
        assert acc_b.paid == 0.0
        assert acc_b.spent == 0.0
        assert acc_b.owed == 0.0

    ledger.add_expense(Expense(payer="A", quantity=10.0, assignment={"B": 1}, concept="More stuff", date=GENERIC_DATE))
    ledger.add_expense(
        Expense(payer="B", quantity=-10.0, assignment={"B": 1}, concept="Another Reimbursement", date=GENERIC_DATE)
    )

    with subtests.test("Test reimbursement to account that didn't pay."):
        assert acc_a.paid == 10.0
        assert acc_a.spent == 0.0
        assert acc_a.owed == -10.0
        assert acc_b.paid == -10.0
        assert acc_b.spent == 0.0
        assert acc_b.owed == 10.0
        assert ledger.settle_transfers == [Transfer("B", 10, "A")]


def test_add_transfer(tmp_path: Path, subtests: pytest.Subtests) -> None:
    out_path = tmp_path / "out.txt"
    ledger = Ledger(file_path=out_path, members=["A", "B"])
    ledger.add_expense(
        Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Stuff", date=GENERIC_DATE)
    )
    ledger.add_transfer(Transfer(payer="B", quantity=5.0, recipient="A", date=GENERIC_DATE))

    with subtests.test("Test add transfer to settle."):
        assert ledger.accounts["A"].paid == 5.0
        assert ledger.accounts["A"].spent == 5.0
        assert ledger.accounts["A"].owed == 0.0
        assert ledger.accounts["B"].paid == 5.0
        assert ledger.accounts["B"].spent == 5.0
        assert ledger.accounts["B"].owed == 0.0

    ledger.add_expense(
        Expense(payer="B", quantity=10.0, assignment={"A": 1, "B": 1}, concept="More stuff", date=GENERIC_DATE)
    )
    ledger.add_transfer(Transfer(payer="A", quantity=10.0, recipient="B", date=GENERIC_DATE))
    with subtests.test("Test add transfer to oversoot."):
        assert ledger.accounts["A"].paid == 15.0
        assert ledger.accounts["A"].spent == 10.0
        assert ledger.accounts["A"].owed == -5.0
        assert ledger.accounts["B"].paid == 5.0
        assert ledger.accounts["B"].spent == 10.0
        assert ledger.accounts["B"].owed == 5.0

    with subtests.test("Add transfer with unknown payer."):
        with pytest.raises(ValueError, match="Transfer payer not in members. 'C'"):
            ledger.add_transfer(Transfer(payer="C", quantity=5.0, recipient="B", date=GENERIC_DATE))

    with subtests.test("Add transfer with unknown recipient."):
        with pytest.raises(ValueError, match="Transfer recipient not in members. 'C'"):
            ledger.add_transfer(Transfer(payer="A", quantity=5.0, recipient="C", date=GENERIC_DATE))


def test_calculate_balance(tmp_path: Path, subtests: pytest.Subtests) -> None:
    ledger_0 = Ledger(file_path=tmp_path / "out_0.txt", members=["A", "B"])
    ledger_0.add_expense(
        Expense(payer="A", quantity=10.0, assignment={"A": 1, "B": 1}, concept="Stuff", date=GENERIC_DATE)
    )
    ledger_0.add_expense(
        Expense(payer="B", quantity=20.0, assignment={"A": 1, "B": 1}, concept="More stuff", date=GENERIC_DATE)
    )
    TARGET_TRANSFERS_0 = [Transfer("A", 5.0, "B")]

    with subtests.test("Calculate balance with two members"):
        assert ledger_0.calculate_balance() == TARGET_TRANSFERS_0

    ledger_1 = Ledger(tmp_path / "out_1.txt", members=["A", "B", "C", "D"])
    ledger_1.add_expense(
        Expense(payer="A", quantity=12.0, assignment={"A": 1, "C": 1, "D": 1}, concept="Stuff", date=GENERIC_DATE)
    )
    ledger_1.add_expense(
        Expense(payer="B", quantity=24.0, assignment={"A": 1, "B": 1, "D": 1}, concept="More stuff", date=GENERIC_DATE)
    )
    TARGET_TRANSFERS_1 = [
        Transfer("C", 4.0, "B"),
        Transfer("D", 12.0, "B"),
    ]

    with subtests.test("Calculate balance with 4 members and 2 transfers"):
        assert sorted(ledger_1.calculate_balance(), key=lambda t: t.quantity) == TARGET_TRANSFERS_1

    ledger_2 = Ledger(tmp_path / "out_2.txt", members=["A", "B", "C", "D"])
    ledger_2.add_expense(
        Expense(
            payer="A", quantity=12.0, assignment={"A": 1, "B": 1, "C": 1, "D": 1}, concept="Stuff", date=GENERIC_DATE
        )
    )
    ledger_2.add_expense(
        Expense(payer="B", quantity=24.0, assignment={"A": 1, "B": 1, "D": 1}, concept="More stuff", date=GENERIC_DATE)
    )
    TARGET_TRANSFERS_2 = [
        Transfer("C", 1.0, "A"),
        Transfer("C", 2.0, "B"),
        Transfer("D", 11.0, "B"),
    ]

    with subtests.test("Calculate balance with 4 members and 3 transfers"):
        assert sorted(ledger_2.calculate_balance(), key=lambda t: t.quantity) == TARGET_TRANSFERS_2

    for transfer in TARGET_TRANSFERS_2:
        ledger_2.add_transfer(transfer)

    with subtests.test("Calculate balance after adding transfers to ledger"):
        assert not ledger_2.calculate_balance()


def test_calculate_balance_symmetric_accounts(tmp_path: Path) -> None:
    ledger_0 = Ledger(file_path=tmp_path / "out_0.txt", members=["A", "B", "C", "D"])
    ledger_0.add_expense(Expense("A", 20.0, "Stuff", {"D": 1}, date=GENERIC_DATE))
    ledger_0.add_expense(Expense("B", 5.0, "More stuff", {"C": 1}, date=GENERIC_DATE))

    TARGET_TRANSFERS_0 = [Transfer("D", 20, "A"), Transfer("C", 5, "B")]

    assert ledger_0.calculate_balance() == TARGET_TRANSFERS_0
