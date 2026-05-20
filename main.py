from expense_share.ledger import Ledger,Expense
import logging
logger = logging.getLogger(__name__)

def test_balance():
    logging.basicConfig(level=logging.DEBUG)
    logger.info("START")

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    ledger = Ledger(members=[A,B,C,D])
    expense_0 = Expense(A, 16.0,distribution={A:1,B:1,C:1,D:1})
    ledger.add_expense(expense_0)

    print("**** Expense 0 ****")
    print(ledger)

    expense_1 = Expense(B, 42.0,distribution={A:1,B:1,C:1,D:1})
    ledger.add_expense(expense_1)

    print("**** Expense 1 ****")
    print(ledger)

    expense_2 = Expense(C, 8.0,distribution={A:0,B:0,C:1,D:1})
    ledger.add_expense(expense_2)

    print("**** Expense 2 ****")
    print(ledger)



if __name__ == "__main__":
    test_balance()
