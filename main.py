   


def update_user_balance(payment,own_part,account,paid,is_payer=False):
    account += payment*own_part
    paid += payment * is_payer
    return account, paid

def test_balance():
    account_A = 0.0
    account_B = 0.0
    paid_A = 0.0
    paid_B = 0.0


    # user A pays
    payment_0 = 10.0
    part_0 = 0.5

    account_A,paid_A = update_user_balance(payment=payment_0,own_part=part_0,account=account_A,paid=paid_A,is_payer=True)
    account_B,paid_B = update_user_balance(payment=payment_0,own_part=1-part_0,account=account_B,paid=paid_B)

    print(f"Payment: account A = {account_A}; account B = {account_B}")
    print(f"       : paid A = {paid_A}; paid B = {paid_B}")
    print(f"Debt A->B: {account_A-paid_A}")
    print()



    # user B pays
    payment_1 = 20.0
    part_1 = 0.5

    account_A,paid_A = update_user_balance(payment=payment_1,own_part=1-part_1,account=account_A,paid=paid_A)
    account_B,paid_B = update_user_balance(payment=payment_1,own_part=part_1,account=account_B,paid=paid_B,is_payer=True)


    print(f"Payment: account A = {account_A}; account B = {account_B}")
    print(f"       : paid A = {paid_A}; paid B = {paid_B}")
    print(f"Debt A->B: {account_A-paid_A}")
    print()

    print("Hello from expense-share!")


if __name__ == "__main__":
    test_balance()
