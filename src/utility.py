from yahoo_fin.stock_info import get_data
import pandas_ta as ta
from datetime import datetime, timedelta
import pandas as pd
from termcolor import colored as cl
import asyncio
import ast
from visualize import visualize_stock
from trade_strategy import *
import queue
import math
from aiofiles import open as aio_open
from watchgod import awatch
import os
from bayes_opt import BayesianOptimization


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

def stock_picker(csv_file, num_stocks=40):
    # Load the data
    df = pd.read_csv(csv_file)

    # Calculate the difference between lower_length and upper_length
    df['length_difference'] = abs(df['upper_length'] - df['lower_length'])

    # Filter and sort the DataFrame
    # Sort first by target in descending order, then by smallest length_difference
    filtered_df = df.sort_values(by=['target', 'length_difference'], ascending=[False, True])

    # Select the top 'num_stocks' stocks
    selected_stocks = filtered_df.head(num_stocks)

    return selected_stocks[['ticker', 'target', 'lower_length', 'upper_length']]

#TODO:
#re-write this to look at the amount of trades made.
def categorize_intensity(lower_length):
    if lower_length < 3:
        return 0 #high
    elif lower_length > 10:
        return 1 #low
    else:
        return 2 #medium
