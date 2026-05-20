from dataclasses import dataclass,field
import logging

logger = logging.getLogger(__name__)

@dataclass
class Account:
    name: str
    spent: float = 0.0
    paid: float = 0.0

    @property
    def owed(self)->float:
        return self.spent - self.paid


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
        
    def __repr__(self)->str:
        return f"Transfer '{self.payer}' -> '{self.recipient}': {self.quantity}."

@dataclass
class Ledger:
    members: list[str]
    accounts: dict[str,Account]= field(init=False)
    
    @property
    def settle_transfers(self)->list[Transfer]:
        return self.calculate_balance()

    def __post_init__(self):
        if len(self.members) <=1:
            raise ValueError("Include at least two members.")

        if len(set(self.members)) < len(self.members):
            raise ValueError("Duplicate member names.")
        
        self.accounts={}
        for name in self.members:
            self.accounts[name] = Account(name=name)

    def __repr__(self)->str:
        out = "Member\tTotal Expenses\tTotal Paid\tOwed"
        for name,account in self.accounts.items():
            out+=f"\n{name}\t{account.spent}\t\t{account.paid}\t\t{account.owed}"
        out+="\nTransfers to settle:"
        for transfer in self.settle_transfers:
            out+=f"\n{transfer}"
        return out
        

    def add_expense(self, expense:Expense)->None:
        if expense.payer not in self.members:
            raise ValueError(f"Expense payer not in members. {expense.payer}")
        if any([m not in self.members for m in expense.distribution]):
            raise ValueError(f"Some recipient not in members.{list(expense.distribution.keys())}")

        payer_account = self.accounts[expense.payer]
        payer_account.paid += expense.quantity

        for name, fraction in expense.distribution.items():
            account = self.accounts[name]
            account.spent += expense.quantity * fraction

    def calculate_balance(self)->list[Transfer]:
        """Calculate who owes money to who.
        
        Sorting the accounts by total amount owed, then assigning transfers between accounts prioritising largest transfers.
        """
        sorted_accounts:list[Account] = sorted(self.accounts.values(),key=lambda a: a.owed,reverse=True)
        logger.debug(f"{dict({a.name:a.owed for a in sorted_accounts})}")
        
        pointer_indebted = 0
        pointer_receiver = len(sorted_accounts)-1

        indebted_account = sorted_accounts[pointer_indebted]
        receiver_account = sorted_accounts[pointer_receiver]
        remaining_owed = indebted_account.owed
        remaining_to_settle = abs(receiver_account.owed)

        settle_transfers = []

        logger.debug(f"rem owed: {remaining_owed} / rem settle {remaining_to_settle}")

        while pointer_indebted < pointer_receiver:
            # Check if we have moved through all the over indebted accounts
            if indebted_account.owed <=0.0:
                break

            if remaining_owed <= remaining_to_settle:
                transfer = Transfer(payer=indebted_account.name,quantity=remaining_owed,recipient=receiver_account.name)
                settle_transfers.append(transfer)
                
                remaining_to_settle-=remaining_owed
                pointer_indebted +=1

                indebted_account = sorted_accounts[pointer_indebted]
                remaining_owed = indebted_account.owed

                logger.debug(f"a transfer {transfer}")
                logger.debug(f"a rem owed: {remaining_owed} / rem settle {remaining_to_settle}")

            else:
                transfer_quantity = remaining_to_settle
                transfer = Transfer(payer=indebted_account.name,quantity=transfer_quantity,recipient=receiver_account.name)
                settle_transfers.append(transfer)
                
                remaining_owed -= transfer_quantity
                pointer_receiver-=1
                
                receiver_account = sorted_accounts[pointer_receiver]
                remaining_to_settle = abs(receiver_account.owed)

                logger.debug(f"b transfer {transfer}")
                logger.debug(f"b rem owed: {remaining_owed} / rem settle {remaining_to_settle}")


        return settle_transfers