import datetime
from io import StringIO
from pathlib import Path

import pytest
from click.testing import CliRunner
from rich.console import Console

from xpsh import VERSION
from xpsh import console
from xpsh.ledger import DATE_OUT_FMT
from xpsh.scripts.main import EXAMPLE_LEDGERS
from xpsh.scripts.main import _resolve_input_path
from xpsh.scripts.main import xpsh


@pytest.fixture
def patch_console(monkeypatch: pytest.MonkeyPatch) -> Console:
    test_console = Console(width=120, file=StringIO())
    monkeypatch.setattr(console, "CONSOLE", test_console)
    return test_console


def _strip_output(content: str) -> str:
    output = []
    for l in content.split("\n"):
        stripped = l.strip()
        if stripped:
            output.append(stripped)
    return "\n".join(output)


def test_resolve_input_path(tmp_path: Path, subtests: pytest.Subtests) -> None:
    file_path_0 = tmp_path / "file_0.txt"
    file_path_0.touch()
    file_path_1 = tmp_path / "file_1.txt"

    with subtests.test("Test resolve path existing file"):
        assert _resolve_input_path(str(file_path_0)) == file_path_0

    with subtests.test("Test resolve path non-existing file"), pytest.raises(SystemExit):
        _resolve_input_path(str(file_path_1))

    with subtests.test("Test resolve path non-existing file ok"):
        assert _resolve_input_path(str(file_path_1), exist_only=False) == file_path_1


def test_resolve_input_path_examples() -> None:
    for kw in EXAMPLE_LEDGERS:
        assert _resolve_input_path(kw).exists()


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(xpsh, ["--version"])
    assert result.output.strip() == VERSION


def test_create(tmp_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = "C,D\n"
    out_path = tmp_path / "out.txt"

    runner = CliRunner()
    result = runner.invoke(xpsh, ["create", str(out_path), "C", "D"])
    with subtests.test("Test cli create new ledger exitcode."):
        assert result.exit_code == 0
    with subtests.test("Test cli create new ledger file output."):
        with open(out_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_create_existing_file(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""

    runner = CliRunner()
    result = runner.invoke(xpsh, ["create", str(example_file_path), "C", "D"])
    with subtests.test("Test cli create new ledger existing file exitcode."):
        assert result.exit_code == 1
    with subtests.test("Test cli create new ledger existing file contents."):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_create_existing_file_force(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = "C,D\n"

    runner = CliRunner()
    result = runner.invoke(xpsh, ["create", str(example_file_path), "C", "D", "--force"])
    with subtests.test("Test cli create new ledger existing file force exitcode."):
        assert result.exit_code == 0
    with subtests.test("Test cli create new ledger existing file force file contents."):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_balance(example_file_path: Path, subtests: pytest.Subtests, patch_console: Console) -> None:
    TARGET_OUTPUT = """Balance
┏━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┓
┃ Member ┃ Total spent ┃ Total paid ┃  Owed ┃
┡━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━┩
│      A │       15.00 │      10.00 │  5.00 │
│      B │       15.00 │      20.00 │ -5.00 │
└────────┴─────────────┴────────────┴───────┘
Transfers to settle
┏━━━━━━┳━━━━┳━━━━━━━━━━┓
┃ From ┃ To ┃ Quantity ┃
┡━━━━━━╇━━━━╇━━━━━━━━━━┩
│    A │  B │     5.00 │
└──────┴────┴──────────┘"""

    runner = CliRunner()
    result = runner.invoke(xpsh, ["balance", str(example_file_path)])

    with subtests.test("Test cli balance exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli balance console output"):
        output = patch_console.file.getvalue()  # ty: ignore[unresolved-attribute]
        assert _strip_output(output) == TARGET_OUTPUT


def test_expenses(example_file_path: Path, subtests: pytest.Subtests, patch_console: Console) -> None:
    TARGET_OUTPUT = """Entries
┏━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Index ┃    Type ┃       Date ┃ Paid by ┃ Quantity ┃    Concept ┃ Assignment / Recipient ┃
┡━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│     0 │ Expense │ 01/01/2000 │       A │    10.00 │      Stuff │ A=50.00%, B=50.00%     │
│     1 │ Expense │ 01/01/2000 │       B │    20.00 │ More stuff │ A=50.00%, B=50.00%     │
└───────┴─────────┴────────────┴─────────┴──────────┴────────────┴────────────────────────┘"""

    runner = CliRunner()
    result = runner.invoke(xpsh, ["expenses", str(example_file_path)])

    with subtests.test("Test cli expenses exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli expenses console output"):
        output = patch_console.file.getvalue()  # ty: ignore[unresolved-attribute]
        assert _strip_output(output) == TARGET_OUTPUT


def test_examples(subtests: pytest.Subtests) -> None:
    runner = CliRunner()
    result = runner.invoke(xpsh, ["examples"])
    with subtests.test("Test cli examples exitcode."):
        assert result.exit_code == 0


def test_search(example_search_file_path: Path, subtests: pytest.Subtests, patch_console: Console) -> None:
    TARGET_OUTPUT = """Entries
┏━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Index ┃     Type ┃       Date ┃ Paid by ┃ Quantity ┃         Concept ┃ Assignment / Recipient ┃
┡━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│     3 │  Expense │ 03/01/2000 │       A │    20.00 │ Even more stuff │ A=50.00%, B=50.00%     │
│     4 │ Transfer │ 03/01/2000 │       A │    10.00 │               - │ B                      │
│     6 │  Expense │ 05/01/2000 │       A │    20.00 │  And more stuff │ A=50.00%, B=50.00%     │
└───────┴──────────┴────────────┴─────────┴──────────┴─────────────────┴────────────────────────┘"""

    runner = CliRunner()
    result = runner.invoke(
        xpsh,
        [
            "search",
            str(example_search_file_path),
            "-p",
            "A",
            "-c",
            "stuff",
            "--from",
            "02/01/2000",
            "--until",
            "05/01/2000",
            "--include-transfers",
        ],
    )

    with subtests.test("Test cli search exitcode."):
        assert result.exit_code == 0
    with subtests.test("Test cli search console output"):
        output = patch_console.file.getvalue()  # ty: ignore[unresolved-attribute]
        assert _strip_output(output) == TARGET_OUTPUT


def test_search_no_hits(example_search_file_path: Path, subtests: pytest.Subtests, patch_console: Console) -> None:
    TARGET_OUTPUT = "No entries found matching the criteria."

    runner = CliRunner()
    result = runner.invoke(xpsh, ["search", str(example_search_file_path), "-p", "A", "-c", "something"])
    with subtests.test("Test cli search exitcode."):
        assert result.exit_code == 0
    with subtests.test("Test cli search console output"):
        output = patch_console.file.getvalue()  # ty: ignore[unresolved-attribute]
        assert _strip_output(output) == TARGET_OUTPUT


def test_add_expense(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
E,01/01/2000,A,25.0,Even more stuff,A:0.5,B:0.5
"""

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


def test_add_reimbursement(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
E,01/01/2000,A,-25.0,Even more stuff,A:0.5,B:0.5
"""

    runner = CliRunner()
    result = runner.invoke(
        xpsh, ["add-reimbursement", str(example_file_path), "A", "25", "Even more stuff", "-d", "01/01/2000"]
    )

    with subtests.test("Test cli add_reimbursement exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add_reimbursement file output"):
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

    runner = CliRunner()
    result = runner.invoke(xpsh, ["add-expense", str(example_file_path), "A", "25", "Even more stuff"])

    with subtests.test("Test cli add_expense exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add_expense file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_add_expense_no_save(example_file_path: Path, subtests: pytest.Subtests, patch_console: Console) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""

    TARGET_OUTPUT = """Balance
┏━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━┓
┃ Member ┃ Total spent ┃ Total paid ┃ Owed ┃
┡━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━┩
│      A │       35.00 │      35.00 │ 0.00 │
│      B │       20.00 │      20.00 │ 0.00 │
└────────┴─────────────┴────────────┴──────┘
The balance is settled!"""

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
        output = patch_console.file.getvalue()  # ty: ignore[unresolved-attribute]
        assert _strip_output(output) == TARGET_OUTPUT


def test_add_transfer(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
T,01/01/2000,A,5.0,B
"""

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

    runner = CliRunner()
    result = runner.invoke(xpsh, ["add-transfer", str(example_file_path), "A", "5", "B"])

    with subtests.test("Test cli add-transfer exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add-transfer file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_add_transfer_no_save(example_file_path: Path, subtests: pytest.Subtests, patch_console: Console) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""

    TARGET_OUTPUT = """Balance
┏━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━┓
┃ Member ┃ Total spent ┃ Total paid ┃ Owed ┃
┡━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━┩
│      A │       15.00 │      15.00 │ 0.00 │
│      B │       15.00 │      15.00 │ 0.00 │
└────────┴─────────────┴────────────┴──────┘
The balance is settled!"""

    runner = CliRunner()
    result = runner.invoke(xpsh, ["add-transfer", str(example_file_path), "A", "5", "B", "-p", "--no-save"])

    with subtests.test("Test cli add-transfer --no-save exitcode"):
        assert result.exit_code == 0

    with subtests.test("Test cli add-transfer --no-save file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT

    with subtests.test("Test cli add-transfer console output"):
        output = patch_console.file.getvalue()  # ty: ignore[unresolved-attribute]
        assert _strip_output(output) == TARGET_OUTPUT


def test_delete_entry(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""

    runner = CliRunner()
    result = runner.invoke(
        xpsh,
        [
            "delete-entry",
            str(example_file_path),
            "0",
            "-y",
        ],
    )
    with subtests.test("Test cli delete exitcode."):
        assert result.exit_code == 0
    with subtests.test("Test cli delete file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_delete_entry_w_prompt(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT_UNMODIFIED = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""

    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""

    runner = CliRunner()
    result = runner.invoke(
        xpsh,
        [
            "delete-entry",
            str(example_file_path),
            "0",
        ],
        input="\n",
    )
    with subtests.test("Test cli delete prompt aborted exitcode."):
        assert result.exit_code == 0
    with subtests.test("Test cli delete prompt aborted file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT_UNMODIFIED

    runner = CliRunner()
    result = runner.invoke(
        xpsh,
        [
            "delete-entry",
            str(example_file_path),
            "0",
        ],
        input="y\n",
    )
    with subtests.test("Test cli delete prompt exitcode."):
        assert result.exit_code == 0
    with subtests.test("Test cli delete prompt file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_delete_entry_out_of_bounds(
    example_file_path: Path, subtests: pytest.Subtests, caplog: pytest.LogCaptureFixture
) -> None:
    TARGET_OUTPUT = "Index does not correspond to a valid entry: 3. Aborting."
    runner = CliRunner()
    result = runner.invoke(
        xpsh,
        [
            "delete-entry",
            str(example_file_path),
            "3",
        ],
    )
    with subtests.test("Test cli delete out of bounds exitcode."):
        assert result.exit_code == 1
    with subtests.test("Test cli delete out of bounds console output"):
        assert TARGET_OUTPUT in caplog.text


def test_edit_entry_prompt(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT_UNMODIFIED = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,15.0,Stuff,A:0.5,B:0.5
E,01/01/2000,B,20.0,More stuff,A:0.5,B:0.5
"""

    runner = CliRunner()
    result = runner.invoke(
        xpsh,
        ["edit-entry", str(example_file_path), "0", "-q", "15"],
        input="\n",
    )
    with subtests.test("Test cli edit entry cancelled exitcode."):
        assert result.exit_code == 0
    with subtests.test("Test cli edit entry cancelled file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT_UNMODIFIED

    runner = CliRunner()
    result = runner.invoke(
        xpsh,
        ["edit-entry", str(example_file_path), "0", "-q", "15"],
        input="y\n",
    )
    with subtests.test("Test cli edit entry prompt exitcode."):
        assert result.exit_code == 0
    with subtests.test("Test cli edit entry prompt file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_edit_entry(example_file_path: Path, subtests: pytest.Subtests) -> None:
    TARGET_FILE_CONTENT = """A,B
E,01/01/2000,A,10.0,Stuff,A:0.5,B:0.5
E,02/01/2000,A,15.0,Other,A:0.75,B:0.25
"""

    runner = CliRunner()
    result = runner.invoke(
        xpsh,
        [
            "edit-entry",
            str(example_file_path),
            "1",
            "-p",
            "A",
            "-q",
            "15",
            "-c",
            "Other",
            "-a",
            "A",
            "3",
            "-a",
            "B",
            "1",
            "-d",
            "02/01/2000",
            "-y",
        ],
        input="\n",
    )
    with subtests.test("Test cli edit entry exitcode."):
        assert result.exit_code == 0
    with subtests.test("Test cli edit entry file output"):
        with open(example_file_path) as f:
            file_content = f.read()
        assert file_content == TARGET_FILE_CONTENT


def test_edit_entry_out_of_bounds(
    example_file_path: Path, subtests: pytest.Subtests, caplog: pytest.LogCaptureFixture
) -> None:
    TARGET_OUTPUT = "Index does not correspond to a valid entry: 3. Aborting."
    runner = CliRunner()
    result = runner.invoke(
        xpsh,
        [
            "edit-entry",
            str(example_file_path),
            "3",
            "-q",
            "15",
        ],
    )
    with subtests.test("Test cli edit entry out of bounds exitcode."):
        assert result.exit_code == 1
    with subtests.test("Test cli edit entry out of bounds console output"):
        assert TARGET_OUTPUT in caplog.text
