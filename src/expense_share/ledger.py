from dataclasses import dataclass,field

@dataclass
class Account:
    name: str
    spent: float = 0.0
    paid: float = 0.0

@dataclass
class Expense:
    payer: str
    quantity: float
    distribution: dict[str,float]

    def __post_init__(self):
        if sum(list(self.distribution.values())) == 1.0:
            return
        
        print("Distribution weights doesn't add up to 1, normalising.")
        total = sum(list(self.distribution.values()))
        for name, value in self.distribution.items():
            self.distribution[name] = value/total

@dataclass
class Transfer:
    payer: str
    quantity: float
    recipient: str

    def __post_init__(self):
        if self.payer == self.recipient:
            raise ValueError("Payer and recipient must be different.")

@dataclass
class Ledger:
    members: list[str] = field(default_factory=list)
    accounts: dict[str,Account]= field(default_factory=dict)

    def __post_init__(self):
        if len(set(self.members)) < len(self.members):
            raise ValueError("Duplicate member names.")
        
        for name in self.members:
            self.accounts[name] = Account(name=name)

    def add_expense(self, expense:Expense)->None:
        if expense.payer not in self.members:
            raise ValueError(f"Expense payer not in members. {expense.payer}")
        if any([m not in self.members for m in expense.distribution]):
            raise ValueError(f"Some expense not in members.{list(expense.distribution.keys())}")

        payer_account = self.accounts[expense.payer]
        payer_account.paid += expense.quantity

        for name, fraction in expense.distribution.items():
            account = self.accounts[name]
            account.spent += expense.quantity * fraction

    def calculate_balance(self)->None:
        pass