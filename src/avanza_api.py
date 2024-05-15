from utility import read_csv, datetime, ChannelType, sleep, initialize_avanza
import asyncio
import backoff
import websockets
import duckdb
import os
import pandas as pd
import time
from threading import Lock
from requests.exceptions import HTTPError

base_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
parquet_file_path = os.path.join(base_path, 'input', f'realtime_data_{datetime.now().strftime("%Y-%m-%d")}_data.parquet')
parquet_lock = Lock()

def init_duckdb_and_parquet():
    global duckdb_conn
    # Reinitialize DuckDB connection
    duckdb_conn = duckdb.connect(database=':memory:')
    duckdb_conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orderbook_data (
            orderbook_id INTEGER,
            buy_price TEXT,
            sell_price TEXT,
            updated_datetime TIMESTAMP
        )
        """
    )
    # Initialize Parquet file if not exists
    if not os.path.exists(parquet_file_path):
        df = pd.DataFrame(columns=['Orderbook ID', 'Buy Price', 'Sell Price', 'Updated Datetime'])
        df.to_parquet(parquet_file_path, index=False)

def write_to_parquet():
    with parquet_lock:
        duckdb_conn.execute(
            f"""
            COPY (SELECT * FROM orderbook_data)
            TO '{parquet_file_path}'
            (FORMAT 'parquet')
            """
        )

def callback(data):
    try:
        orderbook_id = data['data']['orderbookId']
        buy_price = str(data['data']['buyPrice'])
        # sell_price = str(data['data']['sellPrice'])
        updated_timestamp = data['data']['updated']
        updated_datetime = datetime.fromtimestamp(updated_timestamp / 1000.0).strftime('%Y-%m-%d %H:%M:%S')

        # Insert data into DuckDB table
        duckdb_conn.execute(
            "INSERT INTO orderbook_data VALUES (?, ?, ?, ?)",
            (orderbook_id, buy_price, sell_price, updated_datetime)
        )

        # Write to Parquet file
        write_to_parquet()
    except Exception as e:
        print(f"Error during data callback: {e}")

@backoff.on_exception(backoff.expo, websockets.exceptions.ConnectionClosedError, max_tries=8)
async def resilient_subscribe(avanza, whitelisted_tickers):
    await subscribe_to_channel(avanza, whitelisted_tickers)

async def subscribe_to_channel(avanza, whitelisted_tickers):
    for _, id in whitelisted_tickers.items():
        while True:
            try:
                await avanza.subscribe_to_id(ChannelType.QUOTES, str(id), callback)
                break  # Break the loop if subscription is successful
            except websockets.exceptions.ConnectionClosedError as e:
                print(f"WebSocket connection closed unexpectedly: {e}. Reconnecting...")
                await asyncio.sleep(5)  # wait before reconnecting
            except Exception as e:
                print(f"Error subscribing to channel: {e}")
                break  # Exit loop on other exceptions, if appropriate

def main(avanza):
    while True:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            init_duckdb_and_parquet()
            stocks = read_csv(f'{base_path}/input/best_tickers.csv')
            whitelisted_tickers = dict(zip(stocks['ticker'], stocks['id']))
            loop.run_until_complete(resilient_subscribe(avanza, whitelisted_tickers))
            loop.run_forever()
        except HTTPError as e:
            if e.response.status_code == 401:
                print(f"Failed to authenticate: {e}. Retrying in 30 seconds...")
                time.sleep(30)
            else:
                print(f"HTTP error in main: {e}. Retrying in 30 seconds...")
                time.sleep(30)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"WebSocket connection closed unexpectedly: {e}. Restarting...")
        except Exception as e:
            print(f"Error in main: {e}. Retrying in 30 seconds...")
            time.sleep(30)
        finally:
            loop.close()


if __name__ == '__main__':
    while True:
        try:
            avanza = initialize_avanza()
            main(avanza)
        except HTTPError as e:
            if e.response.status_code == 401:
                print(f"Failed to authenticate: {e}. Retrying in 30 seconds...")
                time.sleep(30)
            else:
                print(f"HTTP error during initialization: {e}. Retrying in 30 seconds...")
                time.sleep(30)
        except Exception as e:
            print(f"Error during initialization: {e}. Retrying in 30 seconds...")
            time.sleep(30)
