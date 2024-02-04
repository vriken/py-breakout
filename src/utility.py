from dotenv import load_dotenv
from avanza import Avanza, ChannelType, OrderType
from os import getenv, path
from time import sleep
from pandas import read_csv
from yahoo_fin.stock_info import get_data
from datetime import datetime, timedelta
from math import floor
from termcolor import colored as cl
from watchgod import awatch
from aiofile import async_open as aio_open
from random import randint

avanza = None  # Initialize avanza at the start of your script
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
                sleep(30)  # Wait for 30 seconds before retrying
            else:
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

    
def get_owned_stocks(os):
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
                instrument = entry['instrument']  # Access 'instrument' as a dictionary
                volume = entry['volume']['value']
                orderbook_id = instrument['orderbook']['id']
                orderbook_name = instrument['name']
                
                # Access price information if available
                if 'orderbook' in instrument and 'quote' in instrument['orderbook'] and instrument['orderbook']['quote']['buy'] is not None:
                    buy_price = instrument['orderbook']['quote']['buy']['value']
                    os[orderbook_id] = {'name': orderbook_name, 'price': buy_price, 'shares': volume, 'id': orderbook_id}
                else:
                    break
    else:
        print("No 'withOrderbook' key found in the data dictionary.")
    
    return os  # Return the dictionary containing owned stocks data

def parse_datetime(datetime_str):
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"time data '{datetime_str}' does not match any expected format")

def calculate_brokerage_fee(transaction_amount):
    fee = transaction_amount * 0.0025  # 0.25%
    return max(fee, 1)  # Minimum fee is 1 SEK

async def log_transaction(transaction_type, ticker, orderbook_id, shares, price, transaction_date, profit=None, file_path = '/Users/ake/Documents/probable_spoon_a/output/trades.csv'): #output/trades.csv
    # Parse the transaction date to a datetime object
    transaction_datetime = datetime.strptime(transaction_date, '%Y-%m-%d %H:%M:%S')

    # Check if the transaction time is between 09:00 and 17:00
    if 9 <= transaction_datetime.hour < 17:
        #file_path = 'output/trades.csv'
        header = ['Transaction Type', 'Ticker', 'Orderbook ID', 'Shares', 'Price', 'Date', 'Profit']

        async with aio_open(file_path, 'a') as file:
            # Check if the file is empty and write header if it is
            if (file.tell()) == 0:
                await file.write(','.join(header) + '\n')

            transaction_data = [transaction_type, ticker, str(orderbook_id), str(shares), str(price), transaction_date]

            # Include profit in the log for sell transactions
            if transaction_type == 'SELL' and profit is not None:
                transaction_data.append(str(profit))
            else:
                transaction_data.append('')  # Append empty string for non-sell transactions

            await file.write(','.join(transaction_data) + '\n')