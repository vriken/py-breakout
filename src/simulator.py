import json
from datetime import datetime
from typing import Dict, List, Optional

class SimulatedAccountManager:
    def __init__(self, file_path: str = 'simulated_account.json', initial_balance: float = 100000.0):
        self.file_path = file_path
        self.balance = initial_balance
        self.owned_stocks: Dict[int, Dict[str, float]] = {}
        self.transaction_history: List[Dict[str, str]] = []
        self.load_from_file()  # Load state from file if available

    def get_balance(self) -> float:
        return self.balance

    def get_owned_stocks(self) -> Dict[int, Dict[str, float]]:
        return self.owned_stocks

    def update_balance(self, amount: float) -> None:
        self.balance += amount
        self.record_transaction(0, 'balance_update', 0, amount)
        self.save_to_file()  # Save state after balance update

    def update_owned_stocks(self, orderbook_id: int, shares: int, price: float) -> None:
        if shares > 0:
            self.owned_stocks[orderbook_id] = {'shares': shares, 'price': price}
        else:
            self.owned_stocks.pop(orderbook_id, None)
        self.record_transaction(orderbook_id, 'stock_update', shares, price)
        self.save_to_file()  # Save state after updating owned stocks

    def record_transaction(self, orderbook_id: int, action: str, shares: int, price: float) -> None:
        transaction = {
            'timestamp': datetime.now().isoformat(),
            'orderbook_id': orderbook_id,
            'action': action,
            'shares': shares,
            'price': price
        }
        self.transaction_history.append(transaction)

    def save_to_file(self) -> None:
        try:
            with open(self.file_path, 'w') as f:
                json.dump({
                    'balance': self.balance,
                    'owned_stocks': self.owned_stocks,
                    'transaction_history': self.transaction_history
                }, f, indent=2)
        except IOError as e:
            print(f"Error saving state to file: {e}")

    def load_from_file(self) -> None:
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
                self.balance = data['balance']
                self.owned_stocks = data['owned_stocks']
                self.transaction_history = data.get('transaction_history', [])
        except FileNotFoundError:
            print(f"File {self.file_path} not found. Starting with initial balance.")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading state from file: {e}. Starting with initial balance.")

    def reset(self) -> None:
        self.balance = self.initial_balance
        self.owned_stocks = {}
        self.transaction_history = []
        self.save_to_file()
