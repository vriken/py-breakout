import json

class SimulatedAccountManager:
    def __init__(self, file_path='simulated_account.json', initial_balance=100000):
        self.file_path = file_path
        self.balance = initial_balance
        self.owned_stocks = {}
        self.load_from_file()  # Load state from file if available

    def get_balance(self):
        return self.balance

    def get_owned_stocks(self):
        return self.owned_stocks

    def update_balance(self, amount):
        self.balance += amount
        self.save_to_file()  # Save state after balance update

    def update_owned_stocks(self, orderbook_id, shares, price):
        if shares > 0:
            self.owned_stocks[orderbook_id] = {'shares': shares, 'price': price}
        else:
            del self.owned_stocks[orderbook_id]
        self.save_to_file()  # Save state after updating owned stocks

    def save_to_file(self):
        with open(self.file_path, 'w') as f:
            json.dump({
                'balance': self.balance,
                'owned_stocks': self.owned_stocks
            }, f)

    def load_from_file(self):
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
                self.balance = data['balance']
                self.owned_stocks = data['owned_stocks']
        except FileNotFoundError:
            print(f"File {self.file_path} not found. Starting with initial balance.")
        except json.JSONDecodeError:
            print(f"Error decoding JSON from the file {self.file_path}. Starting with initial balance.")[1][2][3]