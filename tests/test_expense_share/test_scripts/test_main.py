from pathlib import Path

import pytest
from click.testing import CliRunner

from expense_share.scripts.main import xpsh


def test_balance(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_OUTPUT = """Member\tTotal Expenses\tTotal Paid\tOwed
* A\t15.0\t\t10.0\t\t5.0
* B\t15.0\t\t20.0\t\t-5.0

Transfers to settle:
* Transfer 'A' -> 'B': 5.0.
"""

    example_file_path = Path(example_file_path)

    runner = CliRunner()
    result = runner.invoke(xpsh, ["balance", str(example_file_path)])

    with subtests.test("Test cli balance exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli balance console output"):
        assert result.output == TARGET_OUTPUT


def test_add_expense(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
A,10.0,A:0.5,B:0.5
B,20.0,A:0.5,B:0.5
A,25.0,A:0.5,B:0.5
"""

    example_file_path = Path(example_file_path)

    runner = CliRunner()
    result = runner.invoke(xpsh, ["add-expense", str(example_file_path), "A", "25"])

    with subtests.test("Test cli add_expense exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add_expense file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_add_expense_no_save(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
A,10.0,A:0.5,B:0.5
B,20.0,A:0.5,B:0.5
"""

    TARGET_OUTPUT = """Member\tTotal Expenses\tTotal Paid\tOwed
* A\t35.0\t\t35.0\t\t0.0
* B\t20.0\t\t20.0\t\t0.0

Expenses are balanced.
"""

    runner = CliRunner()
    result = runner.invoke(
        xpsh, ["add-expense", str(example_file_path), "A", "25", "-a", "A", "4", "-a", "B", "1", "-p", "--no-save"]
    )

    with subtests.test("Test cli add_expense --no-save exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add_expense --no-save file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT

    with subtests.test("Test cli add_expense console output"):
        assert result.output == TARGET_OUTPUT
