from trade_strategy import *
import ast
from datetime import datetime, timedelta
from visualize import visualize_stock
import pandas as pd
import asyncio
import queue
import math
import asyncio
from aiofiles import open as aio_open
from watchgod import awatch


budget = 2000
current_date = datetime.now()
start_date = current_date - timedelta(weeks = 52 * 2)
start_date_str = start_date.strftime('%Y-%m-%d')
end_date_str = current_date.strftime('%Y-%m-%d')


whitelisted_tickers = {'TRANS.ST': 564938, 'SYSR.ST': 97407, 'SANION.ST': 475457,
                       'CNCJO-B.ST': 5279, 'INDT.ST': 26607, 'INSTAL.ST': 752039,
                       'KDEV.ST': 285632, 'K2A-B.ST': 971402, 'NETI-B.ST': 5440,
                       'NIBE-B.ST': 5325}
whitelisted_tickers_parameters = pd.read_csv('stock_data\\best_whitelisted.csv')

owned_stocks = {}

file_update_queue = queue.Queue()

last_processed_datetime = None

def parse_datetime(datetime_str):
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"time data '{datetime_str}' does not match any expected format")


async def log_transaction(transaction_type, ticker, orderbook_id, shares, price, transaction_date, profit=None):
    # Parse the transaction date to a datetime object
    transaction_datetime = datetime.strptime(transaction_date, '%Y-%m-%d %H:%M:%S')

    # Check if the transaction time is between 09:00 and 17:00
    if 9 <= transaction_datetime.hour < 17:
        file_path = 'output/trades.csv'
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


async def process_realtime_data(realtime_data, tickers, budget):
    global last_processed_datetime

    try:
        # Parse the real-time data (assuming it's a comma-separated string)
        orderbook_id, buy_price, sell_price, datetime_str = realtime_data.split(',')

        # Remove leading and trailing spaces from the datetime string
        datetime_str = datetime_str.strip()

        # Parse the datetime string to a datetime object
        current_datetime = parse_datetime(datetime_str)

        # Check if this datetime is newer than the last processed datetime
        if last_processed_datetime is None or current_datetime > last_processed_datetime:
            # Look up the ticker based on the orderbook ID
            ticker = next((key for key, value in tickers.items() if value == int(orderbook_id)), None)

            if ticker:
                # Get the Donchian channel parameters for this ticker
                params = ast.literal_eval(whitelisted_tickers_parameters.loc[whitelisted_tickers_parameters['ticker'] == ticker]['params'].values[0])

                # Calculate Donchian channels for the ticker based on the parameters
                lower_length = params['lower_length']
                upper_length = params['upper_length']

                # Calculate the start and end dates for historical data (last two years)
                current_date = datetime.now()
                end_date = current_date  # Use the current date as the end date
                start_date = current_date - timedelta(weeks=104)  # Set the start date 2 years (104 weeks) before the end date

                # Get historical data for the ticker for the last two years
                historical_data = await get_historical_data(ticker, start_date_str, end_date_str, "1d")

                # Calculate prices x = lower_length weeks ago and x = upper_length weeks ago
                price_lower_length_weeks_ago = historical_data['close'].iloc[-int(lower_length * 5)]  # Adjust for daily data
                price_upper_length_weeks_ago = historical_data['close'].iloc[-int(upper_length * 5)]  # Adjust for daily data

                # Check for buy and sell signals based on real-time data and Donchian channels
                buy_signal = float(buy_price) > price_lower_length_weeks_ago
                sell_signal = float(sell_price) < price_upper_length_weeks_ago

                # Print the prices x = lower_length weeks ago and x = upper_length weeks ago
                print(f"The price of {ticker}, orderbook id: {orderbook_id}, {lower_length} weeks ago was: {price_lower_length_weeks_ago}")
                print(f"The price of {ticker}, orderbook id: {orderbook_id}, {upper_length} weeks ago was: {price_upper_length_weeks_ago}")

                # Print the current price and buy/sell decision
                current_price = float(buy_price)  # Assuming you want to use the buy price for the current price

                if buy_signal:
                    if ticker not in owned_stocks or owned_stocks[ticker]['shares'] == 0:
                        # Calculate the maximum number of shares that can be bought within the budget
                        max_affordable_shares = math.floor(budget / (current_price * 1.0025))  # Include brokerage fee in calculation
                        if max_affordable_shares > 0:
                            transaction_amount = max_affordable_shares * current_price
                            fee = calculate_brokerage_fee(transaction_amount)

                            owned_stocks[ticker] = {'shares': max_affordable_shares, 'buy_price': current_price}
                            budget -= transaction_amount + fee  # Include brokerage fee
                            await log_transaction('BUY', ticker, orderbook_id, max_affordable_shares, current_price, current_datetime.strftime('%Y-%m-%d %H:%M:%S'))
                            print(f"BUY at {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}: {max_affordable_shares} Shares of {ticker} bought at {current_price} SEK, Fee: {fee} SEK, of which {fee} SEK fee")
                        else:
                            print(f"Budget too low to buy any shares of {ticker}.")
                    else:
                        print(f"Already own {owned_stocks[ticker]['shares']} shares of {ticker}. No action taken.")

                elif sell_signal:
                    if ticker in owned_stocks and owned_stocks[ticker]['shares'] > 0:
                        sell_shares = owned_stocks[ticker]['shares']
                        sell_price = current_price
                        total_sell_amount = sell_shares * sell_price
                        fee = calculate_brokerage_fee(total_sell_amount)

                        total_buy_amount = sell_shares * owned_stocks[ticker]['buy_price']
                        profit = total_sell_amount - total_buy_amount - fee  # Subtract brokerage fee from profit

                        await log_transaction('SELL', ticker, orderbook_id, sell_shares, sell_price, current_datetime.strftime('%Y-%m-%d %H:%M:%S'), profit)
                        print(f"SELL at {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}: {sell_shares} Shares of {ticker} sold at ${sell_price}, Fee: ${fee}, Profit: ${profit - fee}, of which {fee} SEK fee")

                        # Reset the stock entry after selling
                        owned_stocks[ticker]['shares'] = 0
                        owned_stocks[ticker]['buy_price'] = 0
                        budget += total_sell_amount - fee  # Add back the amount after subtracting the fee
                    else:
                        print(f"No shares of {ticker} to sell")
                else:
                    print(f"Today, the price of {ticker} is {current_price}, no action needed.")

            # Update the last processed datetime to the current datetime
            last_processed_datetime = current_datetime

    except Exception as e:
        print(f"Error processing real-time data: {e}")

realtime_data_dir = 'C:\\Users\\vrike\\Documents\\probable-spoon\\probable-spoon\\stock_data'

processed_lines = set()

async def watch_for_data_changes():
    async for changes in awatch(realtime_data_dir):
        for change in changes:
            _, path = change
            if path.endswith('stock_data.txt'):
                async with aio_open(path, 'r') as file:
                    async for line in file:
                        if line.strip() not in processed_lines:
                            processed_lines.add(line.strip())
                            await process_realtime_data(line.strip(), whitelisted_tickers, budget/len(whitelisted_tickers))



# Continuously monitor real-time data changes
async def main():
    await watch_for_data_changes()

asyncio.run(main())
