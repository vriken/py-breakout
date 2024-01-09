from yahoo_fin.stock_info import get_data
import pandas_ta as ta
from datetime import datetime, timedelta
import pandas as pd
from termcolor import colored as cl
import asyncio


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


#TODO:
#re-write this to look at the amount of trades made.
def categorize_intensity(lower_length):
    if lower_length < 3:
        return 0 #high
    elif lower_length > 10:
        return 1 #low
    else:
        return 2 #medium