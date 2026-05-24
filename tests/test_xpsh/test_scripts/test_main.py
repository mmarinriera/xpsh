import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from xpsh.ledger import DATE_OUT_FMT
from xpsh.scripts.main import xpsh


def test_balance(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_OUTPUT = """Balance                                     
┏━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━┓
┃ Member ┃ Total spent ┃ Total paid ┃ Owed ┃
┡━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━┩
│      A │        15.0 │       10.0 │  5.0 │
│      B │        15.0 │       20.0 │ -5.0 │
└────────┴─────────────┴────────────┴──────┘
Transfers to settle     
┏━━━━━━┳━━━━┳━━━━━━━━━━┓
┃ From ┃ To ┃ Quantity ┃
┡━━━━━━╇━━━━╇━━━━━━━━━━┩
│    A │  B │      5.0 │
└──────┴────┴──────────┘
"""

    example_file_path = Path(example_file_path)

    runner = CliRunner()
    result = runner.invoke(xpsh, ["balance", str(example_file_path)])

    with subtests.test("Test cli balance exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli balance console output"):
        assert result.output == TARGET_OUTPUT


def test_expenses(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_OUTPUT = """Entries                                                                            
┏━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃    Type ┃       Date ┃ Paid by ┃ Quantity ┃    Concept ┃ Assignment / Recipient ┃
┡━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Expense │ 01/01/2000 │       A │     10.0 │      Stuff │ A: 50.00%, B: 50.00%   │
│ Expense │ 01/01/2000 │       B │     20.0 │ More stuff │ A: 50.00%, B: 50.00%   │
└─────────┴────────────┴─────────┴──────────┴────────────┴────────────────────────┘
"""

    example_file_path = Path(example_file_path)

    runner = CliRunner()
    result = runner.invoke(xpsh, ["expenses", str(example_file_path)])

    with subtests.test("Test cli balance exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli balance console output"):
        assert result.output == TARGET_OUTPUT


def test_add_expense(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
E,01/01/2000,A,25.0,Even more stuff,A:0.5,B:0.5
"""

    example_file_path = Path(example_file_path)

    runner = CliRunner()
    result = runner.invoke(
        xpsh, ["add-expense", str(example_file_path), "A", "25", "Even more stuff", "-d", "01/01/2000"]
    )

    with subtests.test("Test cli add_expense exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add_expense file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_add_expense_default_date(example_file_path: Path, subtests: pytest.Subtests) -> None:

    current_date = datetime.date.today().strftime(DATE_OUT_FMT)

    TARGET_FILE_CONTENT = f"""A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
E,{current_date},A,25.0,Even more stuff,A:0.5,B:0.5
"""

    example_file_path = Path(example_file_path)

    runner = CliRunner()
    result = runner.invoke(xpsh, ["add-expense", str(example_file_path), "A", "25", "Even more stuff"])

    with subtests.test("Test cli add_expense exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add_expense file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_add_expense_no_save(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""

    TARGET_OUTPUT = """Balance                                     
┏━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━┓
┃ Member ┃ Total spent ┃ Total paid ┃ Owed ┃
┡━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━┩
│      A │        35.0 │       35.0 │  0.0 │
│      B │        20.0 │       20.0 │  0.0 │
└────────┴─────────────┴────────────┴──────┘
The balance is settled!
"""

    runner = CliRunner()
    result = runner.invoke(
        xpsh,
        [
            "add-expense",
            str(example_file_path),
            "A",
            "25",
            "Even more stuff",
            "-a",
            "A",
            "4",
            "-a",
            "B",
            "1",
            "-p",
            "--no-save",
        ],
    )

    with subtests.test("Test cli add_expense --no-save exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add_expense --no-save file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT

    with subtests.test("Test cli add_expense console output"):
        assert result.output == TARGET_OUTPUT


def test_add_transfer(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
T,01/01/2000,A,5.0,B
"""

    example_file_path = Path(example_file_path)

    runner = CliRunner()
    result = runner.invoke(xpsh, ["add-transfer", str(example_file_path), "A", "5", "B", "-d", "01/01/2000"])

    with subtests.test("Test cli add-transfer exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add-transffer file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_add_transfer_default_date(example_file_path: Path, subtests: pytest.Subtests) -> None:
    current_date = datetime.date.today().strftime(DATE_OUT_FMT)

    TARGET_FILE_CONTENT = f"""A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
T,{current_date},A,5.0,B
"""

    example_file_path = Path(example_file_path)

    runner = CliRunner()
    result = runner.invoke(xpsh, ["add-transfer", str(example_file_path), "A", "5", "B"])

    with subtests.test("Test cli add-transfer exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add-transfer file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_add_transfer_no_save(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""

    TARGET_OUTPUT = """Balance                                     
┏━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━┓
┃ Member ┃ Total spent ┃ Total paid ┃ Owed ┃
┡━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━┩
│      A │        15.0 │       15.0 │  0.0 │
│      B │        15.0 │       15.0 │  0.0 │
└────────┴─────────────┴────────────┴──────┘
The balance is settled!
"""

    runner = CliRunner()
    result = runner.invoke(xpsh, ["add-transfer", str(example_file_path), "A", "5", "B", "-p", "--no-save"])

    with subtests.test("Test cli add-transfer --no-save exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add-transfer --no-save file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT

    with subtests.test("Test cli add-transfer console output"):
        assert result.output == TARGET_OUTPUT
