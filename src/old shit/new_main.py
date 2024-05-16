from utility import OrderType, getenv, initialize_avanza, get_balance, get_owned_stocks, read_csv, get_data, datetime, timedelta, floor, calculate_brokerage_fee, randint, ChannelType
import asyncio
import backoff
import websockets
import os
import pandas as pd
import time
from threading import Lock
from dotenv import load_dotenv
from requests.exceptions import HTTPError
from avanza import Avanza, ChannelType, OrderType

def initialize_avanza():
    load_dotenv()

    while True:
        try:
            avanza = Avanza({
                'username': getenv('AVANZA_USERNAME'),
                'password': getenv('AVANZA_PASSWORD'),
                'totpSecret': getenv('AVANZA_TOTP_SECRET')
            })
            return avanza
        except Exception as e:
            if "500" in str(e):
                print("Received a 500 error. Retrying in 30 seconds...\n")
                time.sleep(60)  # Wait for 30 seconds before retrying
            else:
                print(f"Failed to authenticate: {e}")
                time.sleep(10)
                raise e  # If it's not a 500 error, raise the exception

def get_balance():
    global avanza

    try:
        data = avanza.get_overview()
    except:
        avanza = initialize_avanza()
        data = avanza.get_overview()
    
    budget = 0
    for account in data['accounts']:
        if account['id'] == getenv('AVANZA_ACCOUNT_ID'):
            budget = account['balance']['value']
            break
        
    return budget

def get_owned_stocks(owned_stocks_dict):
    global avanza
    
    try:
        data = avanza.get_accounts_positions()
    except:
        avanza = initialize_avanza()
        data = avanza.get_accounts_positions()
    
    if 'withOrderbook' in data:
        for entry in data['withOrderbook']:
            account = entry['account']
            if account['id'] == getenv('AVANZA_ACCOUNT_ID'):
                instrument = entry['instrument']
                volume = entry['volume']['value']
                orderbook_id = instrument['orderbook']['id']
                orderbook_name = instrument['name']
                
                if 'orderbook' in instrument and 'quote' in instrument['orderbook'] and instrument['orderbook']['quote']['buy'] is not None:
                    buy_price = instrument['orderbook']['quote']['buy']['value']
                    owned_stocks_dict[orderbook_id] = {'name': orderbook_name, 'price': buy_price, 'shares': volume, 'id': orderbook_id}
                else:
                    break
    else:
        print("No 'withOrderbook' key found in the data dictionary.")
    
    return owned_stocks_dict

def calculate_brokerage_fee(transaction_amount):
    fee = transaction_amount * 0.0025  # 0.25%
    return max(fee, 1)  # Minimum fee is 1 SEK

load_dotenv()

base_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
data_lock = Lock()
orderbook_data = pd.DataFrame(columns=['orderbook_id', 'buy_price', 'sell_price', 'updated_datetime'])

budget = get_balance()
significant_impact_threshold = 0.25
total_account_value = 4000  # Update this to update automatically
print(f'Initial budget is: {budget}\n')

# Checking which stocks are already owned
owned_stocks = {}
owned_stocks = get_owned_stocks(owned_stocks)
for stock_id, stock_info in owned_stocks.items():
    print(f"{stock_info['name']} - Price: {stock_info['price']}, Shares: {stock_info['shares']} - ID: {stock_info['id']}")

print('\n- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')

# Reading our parameters
stocks = read_csv(f'{base_path}/input/best_tickers.csv')
whitelisted_tickers = dict(zip(stocks['ticker'], stocks['id']))

print('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')


# Getting Donchian parameters
donchian_parameters = {}
for index, row in stocks.iterrows():
    ticker = row['ticker']
    params = {
        'lower_length': row['lower_length'],
        'upper_length': row['upper_length']
    }
    donchian_parameters[ticker] = params


# Preparing for fetching Yahoo data
current_date = datetime.now()
start_date_str = (current_date - timedelta(days=80)).strftime('%Y-%m-%d')
end_date_str = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')

historical_data_dict = {}
# This takes like a minute, figure out a way to store this more effectively
print('Fetching historical data')
for ticker, ticker_id in whitelisted_tickers.items():
    if ticker:
        try:
            # Get historical data for the ticker
            historical_data = get_data(ticker, start_date_str, end_date_str, "1d")
            
            # Extract relevant information and store it in a list of dictionaries
            data_list = []
            for index, row in historical_data.iterrows():
                data = {
                    'high': row['high'],
                    'low': row['low'],
                    'ticker': ticker,
                    'index': index.strftime("%Y-%m-%d")  # Format date as YYYY-MM-DD
                }
                data_list.append(data)
            
            # Store the data list in the historical_data_dict with the ticker as the key
            historical_data_dict[ticker] = data_list

        except Exception as e:
            print(f"Error fetching data for ticker {ticker}: {e}")

print('Done fetching historical data')


# Calculating highest and lowest prices based on the Donchian channel parameters
highest_prices = {}
lowest_prices = {}

for ticker, data_list in historical_data_dict.items():
    # Convert upper_length and lower_length to integers
    upper_length = int(donchian_parameters[ticker]['upper_length'])
    lower_length = int(donchian_parameters[ticker]['lower_length'])
    
    if len(data_list) >= max(upper_length, lower_length):
        recent_high_data = data_list[-upper_length:]
        highest_prices[ticker] = max([data['high'] for data in recent_high_data])
        
        recent_low_data = data_list[-lower_length:]
        lowest_prices[ticker] = min([data['low'] for data in recent_low_data])


def append_data(data):
    global orderbook_data
    with data_lock:
        orderbook_data = pd.concat([orderbook_data, data], ignore_index=True)

def get_data_frame():
    with data_lock:
        return orderbook_data.copy()


async def process_realtime_data(orderbook_id, stock_data, avanza):
    try:
        buy_ask = float(stock_data['buy_price'])
        sell_ask = float(stock_data['sell_price'])
        datetime_obj = stock_data['updated_datetime']

        if datetime_obj is not None:
            if datetime_obj <= (datetime.now() - timedelta(seconds=5)):
                return

        ticker = stock_data.get('ticker')  # Get the ticker from the data
        highest_price = round(highest_prices.get(ticker, 0), 3)
        lowest_price = round(lowest_prices.get(ticker, 0), 3)

        owned_stocks = get_owned_stocks({})
        budget = get_balance()

        # Buy logic
        if orderbook_id not in owned_stocks.keys() or str(orderbook_id) not in owned_stocks.keys():
            max_budget_for_stock = budget
            max_affordable_shares = floor(max_budget_for_stock / sell_ask)
            stock_purchase_impact = (sell_ask + calculate_brokerage_fee(sell_ask)) * max_affordable_shares
            if max_affordable_shares > 0:
                shares_to_buy = max_affordable_shares if stock_purchase_impact < budget * 0.2 else randint(1, max_affordable_shares)
                if shares_to_buy >= 1 and sell_ask > highest_price:
                    transaction_amount = shares_to_buy * sell_ask + calculate_brokerage_fee(shares_to_buy * sell_ask)
                    if transaction_amount <= budget and transaction_amount > 250:  # Ensuring budget sufficiency and minimum transaction amount
                        budget -= transaction_amount  # Update the budget
                        owned_stocks[orderbook_id] = {'price': sell_ask, 'shares': shares_to_buy}
                        current_date = datetime.now()
                        await avanza.place_order(account_id=getenv('AVANZA_ACCOUNT_ID'), order_book_id=orderbook_id, order_type=OrderType.BUY, price=sell_ask, valid_until=current_date.strftime('%Y-%m-%d %H:%M:%S'), volume=shares_to_buy)
                        # await log_transaction('BUY', orderbook_id, shares_to_buy, sell_ask, current_date.strftime('%Y-%m-%d %H:%M:%S'))
                        print(f"BUY {shares_to_buy} shares of {orderbook_id} at {sell_ask}.")
                    else:
                        print(f"Insufficient budget or transaction amount too low for {orderbook_id}.")
                else:
                    print(f"Not buying any shares of {orderbook_id} as calculated shares to buy is less than one.")

        # Sell logic
        elif orderbook_id in owned_stocks and owned_stocks[orderbook_id]['shares'] > 0:
            if buy_ask < lowest_price:
                sell_shares = owned_stocks[orderbook_id]['shares']
                transaction_amount = sell_shares * buy_ask - calculate_brokerage_fee(sell_shares * buy_ask)
                budget += transaction_amount
                
                owned_stocks[orderbook_id]['shares'] = 0
                current_date = datetime.now()
                await avanza.place_order(account_id=getenv('AVANZA_ACCOUNT_ID'), order_book_id=orderbook_id, order_type=OrderType.SELL, price=buy_ask, valid_until=current_date.strftime('%Y-%m-%d %H:%M:%S'), volume=sell_shares)
                # await log_transaction('SELL', orderbook_id, sell_shares, buy_ask, current_date.strftime('%Y-%m-%d %H:%M:%S'))
                print(f"SOLD {sell_shares} shares of {orderbook_id} at {buy_ask}.")
            else:
                print(f"No sell action taken for {orderbook_id} as the price has not met the selling criteria.")

    except Exception as e:
        print(f"Error processing realtime data for orderbook ID {orderbook_id}: {e}")


def callback(data):
    try:
        orderbook_id = data['data']['orderbookId']
        buy_price = str(data['data']['buyPrice'])
        sell_price = str(data['data']['sellPrice'])
        updated_timestamp = data['data']['updated']
        updated_datetime = datetime.fromtimestamp(updated_timestamp / 1000.0).strftime('%Y-%m-%d %H:%M:%S')

        new_data = pd.DataFrame([{
            'orderbook_id': orderbook_id,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'updated_datetime': updated_datetime
        }])

        append_data(new_data)

        # Execute buy/sell logic
        asyncio.create_task(process_realtime_data(orderbook_id, {
            'buy_price': buy_price,
            'sell_price': sell_price,
            'updated_datetime': datetime.fromtimestamp(updated_timestamp / 1000.0),
            'ticker': data.get('ticker')
        }, avanza))

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
