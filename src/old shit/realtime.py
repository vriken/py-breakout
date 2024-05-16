from utility import OrderType, getenv, initialize_avanza, get_balance, get_owned_stocks, read_csv, get_data, datetime, timedelta, floor, calculate_brokerage_fee, randint, read_parquet, DataFrame
import asyncio
import pyarrow
import duckdb
import os
from dotenv import load_dotenv
load_dotenv()

base_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
parquet_file_path = os.path.join(base_path, 'input', f'realtime_data_{datetime.now().strftime("%Y-%m-%d")}_data.parquet')

budget = get_balance()
significant_impact_threshold = 0.25
total_account_value = 4000  # Update this to update automatically
print(f'Initial budget is: {budget}\n')

# Checking which stocks we already own
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
print(budget)
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

async def process_realtime_data(orderbook_id, stock_data, avanza):
    try:
        buy_ask = float(stock_data['buy_price'])
        sell_ask = float(stock_data['sell_price'])
        datetime_obj = stock_data['updated']

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
                        await avanza.place_order(account_id=getenv('AVANZA_ACCOUNT_ID'), order_book_id=orderbook_id,order_type=OrderType.BUY, price=sell_ask, valid_until=current_date.strftime('%Y-%m-%d %H:%M:%S'), volume=shares_to_buy)
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
                await avanza.place_order(account_id=getenv('AVANZA_ACCOUNT_ID'), order_book_id=orderbook_id,order_type=OrderType.SELL, price=buy_ask, valid_until=current_date.strftime('%Y-%m-%d %H:%M:%S'), volume=sell_shares)
                # await log_transaction('SELL', orderbook_id, sell_shares, buy_ask, current_date.strftime('%Y-%m-%d %H:%M:%S'))
                print(f"SOLD {sell_shares} shares of {orderbook_id} at {buy_ask}.")
            else:
                print(f"No sell action taken for {orderbook_id} as the price has not met the selling criteria.")

    except Exception as e:
        print(f"Error processing realtime data for orderbook ID {orderbook_id}: {e}")

async def watch_for_data_changes():
    # duckdb_conn = duckdb.connect(database=':memory:')
    avanza = initialize_avanza()
    last_processed = {}  # Dictionary to track the last processed timestamp for each key

    try:
        while True:
            # Read the Parquet file into a DataFrame
            if os.path.exists(parquet_file_path):
                stock_data_df = read_parquet(parquet_file_path)
                
                # Iterate over each row in the DataFrame
                for _, row in stock_data_df.iterrows():
                    key = str(row.get('orderbook_id'))  # Use .get() to avoid KeyError
                    timestamp_obj = row.get('updated_datetime')

                    if timestamp_obj is not None:
                        data_timestamp = timestamp_obj
                    else:
                        data_timestamp = None
                    
                    if key not in last_processed or (data_timestamp and last_processed[key] < data_timestamp):
                        stock_data = {
                            'orderbook_id': row.get('orderbook_id'),
                            'buy_price': row.get('buy_price'),
                            'sell_price': row.get('sell_price'),
                            'updated': data_timestamp,
                            'ticker': row.get('ticker')
                        }
                        await process_realtime_data(key, stock_data, avanza)
                        if data_timestamp:
                            last_processed[key] = data_timestamp

            await asyncio.sleep(1)  # Adjust the sleep duration as necessary

    except Exception as e:
        print(f"An error occurred: {e}")


async def main():
    """Entry point for the realtime module when called from main.py."""
    await watch_for_data_changes()

if __name__ == "__main__":
    asyncio.run(main())