import os
import pandas as pd
from datetime import datetime
from pandas import DataFrame
import duckdb
from threading import Lock

# Base path and Parquet file path
base_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
parquet_file_path = os.path.join(base_path, 'output', 'trades.parquet')
parquet_lock = Lock()

# Initialize DuckDB connection
duckdb_conn = duckdb.connect(database=':memory:')

def init_duckdb_and_parquet():
    global duckdb_conn
    # Reinitialize DuckDB connection
    duckdb_conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_type TEXT,
            orderbook_id INTEGER,
            shares INTEGER,
            price FLOAT,
            transaction_date TIMESTAMP
        )
        """
    )
    # Initialize Parquet file if not exists
    if not os.path.exists(parquet_file_path):
        df = pd.DataFrame(columns=['Transaction Type', 'Orderbook ID', 'Shares', 'Price', 'Date'])
        os.makedirs(os.path.dirname(parquet_file_path), exist_ok=True)
        df.to_parquet(parquet_file_path, index=False)

def write_to_parquet():
    with parquet_lock:
        duckdb_conn.execute(
            f"""
            COPY (SELECT * FROM transactions)
            TO '{parquet_file_path}'
            (FORMAT 'parquet')
            """
        )

async def log_transaction(transaction_type, orderbook_id, shares, price, transaction_date):
    transaction_datetime = datetime.strptime(transaction_date, '%Y-%m-%d %H:%M:%S')

    if 9 <= transaction_datetime.hour < 17:
        init_duckdb_and_parquet()

        # Insert data into DuckDB table
        duckdb_conn.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?)",
            (transaction_type, int(orderbook_id), int(shares), float(price), transaction_datetime)
        )

        # Write to Parquet file
        write_to_parquet()

        print(f"Logged transaction: {transaction_type}, {orderbook_id}, {shares}, {price}, {transaction_date}")
