# main.py
from os import path
import asyncio
from datetime import datetime, timedelta
from avanza_initializer import AvanzaInitializer
from account_manager import AccountManager
from data_manager import DataManager
from trading_logic import TradingLogic
from websocket_subscription import WebSocketSubscription
from requests.exceptions import HTTPError
from websockets.exceptions import ConnectionClosedError
from dotenv import load_dotenv
from time import sleep
import pandas as pd
from yahoo_fin.stock_info import get_data

def main():
    load_dotenv()
    base_path = path.dirname(path.dirname(path.realpath(__file__)))

    try:
        # Initialize Avanza
        avanza = AvanzaInitializer.initialize_avanza()

        # Initialize managers
        account_manager = AccountManager(avanza)
        data_manager = DataManager(base_path)
        trading_logic = TradingLogic(avanza, account_manager, data_manager)

        # Read stocks and prepare whitelisted tickers
        stocks = data_manager.read_csv(f'{base_path}/input/best_tickers.csv')
        whitelisted_tickers = dict(zip(stocks['ticker'], stocks['id']))

        # Prepare for fetching Yahoo data
        current_date = datetime.now()
        start_date_str = (current_date - timedelta(days=80)).strftime('%Y-%m-%d')
        end_date_str = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')

        historical_data_dict = {}
        donchian_parameters = {}
        
        print('fetching historical data from yahoo')
        for index, row in stocks.iterrows():
            orderbook_id = int(row['id'])  # Ensure orderbook_id is an integer
            params = {
                'lower_length': row['lower_length'],
                'upper_length': row['upper_length']
            }
            donchian_parameters[orderbook_id] = params

            try:
                historical_data = get_data(row['ticker'], start_date_str, end_date_str, "1d")
                data_list = [{
                    'high': row['high'],
                    'low': row['low'],
                    'orderbook_id': orderbook_id,
                    'index': index.strftime("%Y-%m-%d")
                } for index, row in historical_data.iterrows()]

                historical_data_dict[orderbook_id] = data_list

            except Exception as e:
                print(f"Error fetching data for orderbook ID {orderbook_id}: {e}")
        print('DONE fetching historical data from yahoo')

        trading_logic.calculate_donchian_channels(historical_data_dict, donchian_parameters)

        # Define callback function for WebSocket
        def callback(data):
            try:
                orderbook_id = int(data['data']['orderbookId'])  # Ensure orderbook_id is an integer
                buy_price = str(data['data']['buyPrice'])
                sell_price = str(data['data']['sellPrice'])
                updated_timestamp = data['data']['updated']
                updated_datetime = datetime.fromtimestamp(updated_timestamp / 1000.0)

                # Execute buy/sell logic
                asyncio.create_task(trading_logic.process_realtime_data(orderbook_id, {
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'updated_datetime': updated_datetime  # Pass as datetime object
                }))

            except Exception as e:
                print(f"Error during data callback: {e}")

        # Initialize WebSocket subscription
        websocket_subscription = WebSocketSubscription(avanza, whitelisted_tickers, callback)

        while True:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(websocket_subscription.resilient_subscribe())
                loop.run_forever()
            except HTTPError as e:
                if e.response.status_code == 401:
                    print(f"Failed to authenticate: {e}. Retrying in 30 seconds...")
                    sleep(30)
                else:
                    print(f"HTTP error in main: {e}. Retrying in 30 seconds...")
                    sleep(30)
            except ConnectionClosedError as e:
                print(f"WebSocket connection closed unexpectedly: {e}. Restarting...")
            except Exception as e:
                print(f"Error in main: {e}. Retrying in 30 seconds...")
                sleep(30)
            finally:
                loop.close()

    except HTTPError as e:
        if e.response.status_code == 401:
            print(f"Failed to authenticate: {e}. Retrying in 30 seconds...")
            sleep(30)
        else:
            print(f"HTTP error during initialization: {e}. Retrying in 30 seconds...")
            sleep(30)
    except Exception as e:
        print(f"Error during initialization: {e}. Retrying in 30 seconds...")
        sleep(30)

if __name__ == '__main__':
    main()
