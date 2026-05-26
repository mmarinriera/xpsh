# XPSH (eXPense-SHare)

`xpsh` is a simple expense sharing tool to keep track of common expenses and transfers between a group of people,
e.g. a group of friends going on a trip.

`xpsh` can be directly used via the command line interface, or as a third party module via the API.

## Installation

Using `pip`:

```bash
pip install git+https://github.com/mmarinriera/xpsh
```
or, alternatively, add the following line to your `requirements.txt`:

```
git+https://github.com/mmarinriera/xpsh
```

Using `uv`:

Install as a third party package to your project:

```bash
uv add git+https://github.com/mmarinriera/xpsh
```

Install as a standalone tool:

```bash
uv tool install git+https://github.com/mmarinriera/xpsh
```

## Usage

Run `xpsh --help` after installation to check the CLI documentation.

### CLI example

Create a new ledger with 4 members and add some expenses.

```bash
$ xpsh create tmnt.xpsh Leonardo Donatello Raphael Michelangelo
$ xpsh add-expense tmnt.xpsh Leonardo 20 Pizza
$ xpsh add-expense tmnt.xpsh Donatello 20 Nunchuks -a Donatello 1 -a Michelangelo 3
```
Check the balance.
```bash
$ xpsh balance tmnt.xpsh
Balance                                            
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┓
┃       Member ┃ Total spent ┃ Total paid ┃  Owed ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━┩
│     Leonardo │         5.0 │       20.0 │ -15.0 │
│    Donatello │        10.0 │       20.0 │ -10.0 │
│      Raphael │         5.0 │        0.0 │   5.0 │
│ Michelangelo │        20.0 │        0.0 │  20.0 │
└──────────────┴─────────────┴────────────┴───────┘
Transfers to settle                    
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃         From ┃        To ┃ Quantity ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ Michelangelo │  Leonardo │     15.0 │
│ Michelangelo │ Donatello │      5.0 │
│      Raphael │ Donatello │      5.0 │
└──────────────┴───────────┴──────────┘
```

Add transfers to settle the balance:

```bash
$ xpsh add-transfer tmnt.xpsh Michelangelo 15 Leonardo
$ xpsh add-transfer tmnt.xpsh Michelangelo 5 Donatello
$ xpsh add-transfer tmnt.xpsh Raphael 5 Donatello
```

Balance is settled:

```bash
$ xpsh balance tmnt.xpsh
Balance                                           
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━┓
┃       Member ┃ Total spent ┃ Total paid ┃ Owed ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━┩
│     Leonardo │         5.0 │        5.0 │  0.0 │
│    Donatello │        10.0 │       10.0 │  0.0 │
│      Raphael │         5.0 │        5.0 │  0.0 │
│ Michelangelo │        20.0 │       20.0 │  0.0 │
└──────────────┴─────────────┴────────────┴──────┘
The balance is settled!
```

## Development

Clone the repository and install project,

```bash
git clone https://github.com/mmarinriera/xpsh.git
cd xpsh
uv sync --group dev
```
Use `pre-commit` or `prek` to install pre-commit hooks (formatting, linting, type-checking),

```bash
uv sync --group dev
prek install
prek install --hook-type commit-msg
```
and use `tox` to run tests with coverage.
