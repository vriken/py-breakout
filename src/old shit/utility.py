from dotenv import load_dotenv
import avanza
from avanza import Avanza, ChannelType, OrderType
from os import getenv, path, makedirs
from time import sleep
import csv
from pandas import read_csv, DataFrame, to_datetime, Timestamp, read_parquet, concat
from yahoo_fin.stock_info import get_data
from datetime import datetime, timedelta
from math import floor
from termcolor import colored as cl
from watchgod import awatch
from aiofile import async_open as aio_open
from bayes_opt import BayesianOptimization
from random import randint
import pandas_ta as ta
import redis.asyncio as aioredis

# avanza = None  # Initialize avanza at the start of your script
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
                sleep(60)  # Wait for 30 seconds before retrying
            else:
                print(f"Failed to authenticate: {e}")
                sleep(10)
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

async def log_transaction(transaction_type, orderbook_id, shares, price, transaction_date, output_file_path):
    transaction_datetime = datetime.strptime(transaction_date, '%Y-%m-%d %H:%M:%S')

    if 9 <= transaction_datetime.hour < 17:
        header = ['Transaction Type', 'Orderbook ID', 'Shares', 'Price', 'Date']
        transaction_data = [transaction_type, int(orderbook_id), int(shares), float(price), transaction_date]

        new_transaction_df = DataFrame([transaction_data], columns=header)

        # Ensure the Parquet file is initialized
        if not path.exists(output_file_path):
            header = ['Transaction Type', 'Orderbook ID', 'Shares', 'Price', 'Date']
            df = DataFrame(columns=header)
            makedirs(path.dirname(output_file_path), exist_ok=True)
            df.to_parquet(output_file_path, index=False)

        if path.exists(output_file_path):
            existing_transactions_df = read_parquet(output_file_path)
            updated_transactions_df = concat([existing_transactions_df, new_transaction_df], ignore_index=True)
        else:
            # This case should not be hit due to init_parquet_file, but handle it defensively
            updated_transactions_df = new_transaction_df

        updated_transactions_df.to_parquet(output_file_path, index=False)
        print(f"Logged transaction: {transaction_data}")


            
def implement_strategy(stock, investment, lower_length=None, upper_length=None):
    actions = []
    in_position = False
    equity = investment
    no_of_shares = 0

    for i in range(3, len(stock)):
        current_entry = stock['date'].iloc[i]

        if isinstance(current_entry, Timestamp):
            # This is a datetime object, can be used directly or formatted
            current_date_or_datetime = current_entry.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # This is likely a date object or another format, use as is or convert/format accordingly
            current_date_or_datetime = str(current_entry)

        # Buy
        if stock['high'].iloc[i] >= stock['dcu'].iloc[i] and not in_position:
            no_of_shares = equity // stock.close.iloc[i]
            equity -= no_of_shares * stock.close.iloc[i]
            in_position = True
            actions.append({'Date': current_date_or_datetime, 'Action': 'BUY', 'Shares': no_of_shares, 'Price': stock.close.iloc[i], 'Volume': stock.volume.iloc[i]})
            fee = calculate_brokerage_fee(no_of_shares * stock.close.iloc[i])
            equity -= fee  # Deducting the transaction fee

        # Sell
        elif stock['low'].iloc[i] <= stock['dcl'].iloc[i] and in_position:
            equity += no_of_shares * stock.close.iloc[i]
            in_position = False
            actions.append({'Date': current_date_or_datetime, 'Action': 'SELL', 'Shares': no_of_shares, 'Price': stock.close.iloc[i], 'Volume': stock.volume.iloc[i]})
            fee = calculate_brokerage_fee(no_of_shares * stock.close.iloc[i])
            equity -= fee  # Deducting the transaction fee

    # Close
    if in_position:
        equity += no_of_shares * stock['close'].iloc[-1]
        in_position = False
        fee = calculate_brokerage_fee(no_of_shares * stock['close'].iloc[-1])
        equity -= fee  # Deducting the transaction fee

    earning = round(equity - investment, 2)

    return actions, equity, earning

def extract_ids_and_update_csv(input_file_path, output_file_path):
    with open(input_file_path, mode='r') as infile, open(output_file_path, mode='w', newline='') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ['id']  # Add 'id' to the existing field names
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            ticker = row['ticker'].split('.')[0]  # Remove the '.ST' part
            result = avanza.search_for_stock(ticker, 1)
            
            if result['totalNumberOfHits'] > 0:
                row['id'] = result['hits'][0]['topHits'][0]['id']
            else:
                row['id'] = 'Not Found'
            
            writer.writerow(row)