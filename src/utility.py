from yahoo_fin.stock_info import get_data
import argparse
from pandas_ta import donchian
import pandas_ta as ta
from datetime import datetime, timedelta
import pandas as pd
from termcolor import colored as cl
import asyncio
import ast
import time
from visualize import visualize_stock
import queue
import math
from aiofiles import open as aio_open
from watchgod import awatch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import csv
from bayes_opt import BayesianOptimization
from avanza import Avanza, ChannelType, OrderType
from dotenv import load_dotenv

def implement_strategy(stock, investment, lower_length=None, upper_length=None):
    actions = []
    in_position = False
    equity = investment
    no_of_shares = 0

    # Remove 'date' column processing from here
    # Instead, use the index as the date

    for i in range(3, len(stock)):
        current_entry = stock['date'].iloc[i]

        if isinstance(current_entry, pd.Timestamp):
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

load_dotenv()
#avanza = Avanza({
#    'username': os.getenv('AVANZA_USERNAME'),
#    'password': os.getenv('AVANZA_PASSWORD'),
#    'totpSecret': os.getenv('AVANZA_TOTP_SECRET')
#})

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
            
#extract_ids_and_update_csv('/Users/ake/Documents/probable_spoon/input/best_tickers_without_id.csv', '/Users/ake/Documents/probable_spoon/input/best_tickers.csv')

async def log_transaction(transaction_type, ticker, orderbook_id, shares, price, transaction_date, profit=None, file_path = 'output/trades.csv'):
    # Parse the transaction date to a datetime object
    transaction_datetime = datetime.strptime(transaction_date, '%Y-%m-%d %H:%M:%S')

    # Check if the transaction time is between 09:00 and 17:00
    if 9 <= transaction_datetime.hour < 17:
        #file_path = 'output/trades.csv'
        header = ['Transaction Type', 'Ticker', 'Orderbook ID', 'Shares', 'Price', 'Date', 'Profit']

        async with aio_open(file_path, 'a', newline='') as file:
            # Check if the file is empty and write header if it is
            if (await file.tell()) == 0:
                await file.write(','.join(header) + '\n')

            transaction_data = [transaction_type, ticker, str(orderbook_id), str(shares), str(price), transaction_date]

            # Include profit in the log for sell transactions
            if transaction_type == 'SELL' and profit is not None:
                transaction_data.append(str(profit))
            else:
                transaction_data.append('')  # Append empty string for non-sell transactions

            await file.write(','.join(transaction_data) + '\n')

async def get_historical_data(ticker, start_date, end_date, interval):
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, get_data, ticker, start_date, end_date, True, interval)
    data = data.reset_index().rename(columns={'index': 'date'})
    return data

def get_historical_data_sync(ticker, start_date, end_date, interval):
    return asyncio.run(get_historical_data(ticker, start_date, end_date, interval))

def calculate_brokerage_fee(transaction_amount):
    fee = transaction_amount * 0.0025  # 0.25%
    return max(fee, 1)  # Minimum fee is 1 SEK

def distribute_budget(stock_prices, budget):
    # Sort stocks by price
    sorted_stocks = sorted(stock_prices.items(), key=lambda x: x[1])
    owned_shares = {stock: 0 for stock, price in sorted_stocks}

    # Buy at least one share of each stock, starting with the cheapest
    for stock, price in sorted_stocks:
        if budget >= price:
            owned_shares[stock] += 1
            budget -= price
        else:
            break  # Stop if we can't afford even one share of the current stock

    # Distribute remaining budget for additional shares
    while budget >= sorted_stocks[0][1]:
        for stock, price in sorted_stocks:
            if budget >= price and owned_shares[stock] > 0:  # Only consider stocks already bought
                owned_shares[stock] += 1
                budget -= price
            if budget < sorted_stocks[0][1]:  # Break if not enough budget for the cheapest stock
                break

    return owned_shares, budget

def stock_picker(csv_file, num_stocks=40, output_csv_file='selected_stocks.csv'):
    # Load the data
    df = pd.read_csv(csv_file)

    # Calculate the difference between lower_length and upper_length
    df['length_difference'] = abs(df['upper_length'] - df['lower_length'])

    # Filter and sort the DataFrame
    # Sort first by target in descending order, then by smallest length_difference
    filtered_df = df.sort_values(by=['target', 'length_difference'], ascending=[False, True])

    # Select the top 'num_stocks' stocks
    selected_stocks = filtered_df.head(num_stocks)

    # Write selected stocks to the output CSV file
    selected_stocks[['ticker', 'target', 'lower_length', 'upper_length', 'id']].to_csv(output_csv_file, index=False)

# Call the function to select and write the top 30 stocks to 'selected_stocks.csv'
#stock_picker('/Users/ake/Documents/probable_spoon/output/all_tickers.csv', 50, '/Users/ake/Documents/probable_spoon/output/selected_stocks.csv')


#TODO:
#re-write this to look at the amount of trades made.
def categorize_intensity(lower_length):
    if lower_length < 3:
        return 0 #high
    elif lower_length > 10:
        return 1 #low
    else:
        return 2 #medium
    
    