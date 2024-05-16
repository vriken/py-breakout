import os
import pandas as pd
from threading import Lock

class DataManager:
    def __init__(self, base_path):
        self.base_path = base_path
        self.data_lock = Lock()
        self.orderbook_data = pd.DataFrame(columns=['orderbook_id', 'buy_price', 'sell_price', 'updated_datetime'])

    def append_data(self, data):
        with self.data_lock:
            self.orderbook_data = pd.concat([self.orderbook_data, data], ignore_index=True)

    def get_data_frame(self):
        with self.data_lock:
            return self.orderbook_data.copy()

    def read_csv(self, file_path):
        return pd.read_csv(file_path)

# Example usage:
# data_manager = DataManager(base_path)
# stocks = data_manager.read_csv(f'{base_path}/input/best_tickers.csv')
