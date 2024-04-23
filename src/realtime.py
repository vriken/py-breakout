from utility import get_balance, get_owned_stocks, read_csv, parse_datetime, get_data, datetime, timedelta, floor, calculate_brokerage_fee, log_transaction, cl, awatch, aio_open, randint
import asyncio

budget = get_balance()
significant_impact_threshold = 0.25
total_account_value = 4000 #update this to update automatically
print(f'Initial budget is: {budget}\n')

# checking which stocks we already own
owned_stocks = {}
owned_stocks = get_owned_stocks(owned_stocks)
for stock_id, stock_info in owned_stocks.items():
    print(f"{stock_info['name']} - Price: {stock_info['price']}, Shares: {stock_info['shares']} - ID: {stock_info['id']}")
    
print('\n- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')

# reading our parameters
#stocks = read_csv('./input/best_tickers.csv')
stocks = read_csv('/Users/ake/Documents/probable_spoon_a/input/best_tickers.csv')
whitelisted_tickers = dict(zip(stocks['ticker'], stocks['id']))

# this doesnt work right now
# flagging for any stocks in the avanza data, not in the yahoo data
#for stock_id in owned_stocks.keys():
#    if stock_id not in tickers.values():
#        print(f"Stock with ID {stock_id} is owned, but not tracked.")
        
print('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')

# getting donchian parameters
donchian_parameters = {}
for index, row in stocks.iterrows():
    ticker = row['ticker']
    params = {
        'lower_length': row['lower_length'],
        'upper_length': row['upper_length']
    }
    donchian_parameters[ticker] = params

# preparing for fetching yahoo data
current_date = datetime.now()
start_date_str = (current_date - timedelta(days = 80)).strftime('%Y-%m-%d')
#start_date_str = (current_date - timedelta(days = max(int(donchian_parameters[ticker]['upper_length'])))).strftime('%Y-%m-%d')
end_date_str = (current_date - timedelta(days = 1)).strftime('%Y-%m-%d')

historical_data_dict = {}
# This takes like a minute, figure out a way to store this more effectively
print(budget)
print('fetching historical data')
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
            # Log the error or handle it as needed
            print(f"Error fetching data for ticker {ticker}: {e}")
            # Optionally, continue to next ticker or perform other error recovery actions

print('Done fetching historical data')

        
#print(historical_data_dict)
        
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
        

async def process_realtime_data(data, ticker, budget):
    try:
        orderbook_id, buy_ask, sell_ask, datetime_str = data.split(',')
        ticker = next((key for key, value in ticker.items() if value == int(orderbook_id)), None)
        
        if ticker:            
            datetime_str = datetime_str.strip()
            datetime_obj = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            
            if datetime_obj <= (datetime.now() - timedelta(seconds=5)):
                return
            
            # Rounding to 3 so that we can get the buy order in before the price actually hits.
            highest_price = round(highest_prices.get(ticker), 3)
            lowest_price = round(lowest_prices.get(ticker), 3)
            
            buy_ask = float(buy_ask)
            sell_ask = float(sell_ask)

            # Buy logic
            if orderbook_id not in owned_stocks.keys() or str(orderbook_id) not in owned_stocks.keys():
                max_budget_for_stock = get_balance()
                sell_ask_price = sell_ask 
                max_affordable_shares = floor(max_budget_for_stock / sell_ask_price)
                
                stock_purchase_impact = (sell_ask_price + calculate_brokerage_fee(sell_ask_price)) * max_affordable_shares
                if max_affordable_shares > 0:
                    if stock_purchase_impact < total_account_value * significant_impact_threshold:
                        shares_to_buy = max_affordable_shares
                    else:
                        min_range = max(1, max_affordable_shares // 2)  # Ensures we buy at least 1 share
                        shares_to_buy = randint(min_range, max_affordable_shares)
                    
                    if sell_ask_price > highest_price and shares_to_buy >= 1:
                        transaction_amount = shares_to_buy * sell_ask_price + calculate_brokerage_fee(shares_to_buy * sell_ask_price)
                        
                        # Added check to ensure the budget is sufficient
                        if transaction_amount <= budget:
                            if transaction_amount > 250:
                                budget = budget + transaction_amount - calculate_brokerage_fee(shares_to_buy * sell_ask_price)
                                
                                owned_stocks[orderbook_id] = {
                                    'name': ticker,
                                    'price': sell_ask_price,
                                    'shares': shares_to_buy,
                                    'id': orderbook_id
                                }
                                
                                current_date = datetime.now()
                                await log_transaction('BUY', ticker, orderbook_id, shares_to_buy, sell_ask_price, current_date.strftime('%Y-%m-%d %H:%M:%S'))
                                # print(f"At {current_date.strftime('%Y-%m-%d %H:%M:%S')}, {ticker} with id {orderbook_id} is {sell_ask_price}. The highest price within the specified days was {highest_price}")
                                print(cl(f"At {current_date.strftime('%Y-%m-%d %H:%M:%S')}, we BUY {shares_to_buy} shares of {ticker} at {sell_ask_price} for a total of {transaction_amount} SEK, of which {calculate_brokerage_fee(shares_to_buy * sell_ask_price)} SEK fee", 'green'))
                                # print(f"New budget: {budget}")
                            else:
                                print(f"Transaction amount {transaction_amount} SEK is below the minimum required amount of 250 SEK for purchasing {ticker}.")
                        else:
                            print(f"Not enough budget to buy {shares_to_buy} shares of {ticker} at {sell_ask_price} SEK each. Required: {transaction_amount} SEK, Available: {budget} SEK.")

                    else:
                        print(f'No buy action taken for {ticker} at {datetime_str}. Sell ask price {sell_ask_price} does not exceed the highest price {highest_price} within the threshold.')
                else:
                    print(f'No budget available for purchasing {ticker} at {datetime_str}.')
            # Sell logic
            elif orderbook_id in owned_stocks and owned_stocks[orderbook_id]['shares'] > 0:
                if(buy_ask < lowest_price):
                    sell_shares = owned_stocks[orderbook_id]['shares']
                    sell_price = buy_ask
                    
                    transaction_amount = sell_shares * sell_price
                    budget = budget + transaction_amount - calculate_brokerage_fee(sell_shares * sell_price)
                    owned_stocks[orderbook_id]['shares'] = 0
                    
                    current_date = datetime.now()
                    await log_transaction('SELL', ticker, orderbook_id, sell_shares, sell_price, current_date.strftime('%Y-%m-%d %H:%M:%S'))
                    # print(f"At {datetime_str}, {ticker} with id {orderbook_id} is {buy_ask}. The lowest price within {lower_length} days was {lowest_price}, therefore")
                    print(cl(f"At {datetime_str}, we SELL {sell_shares} shares of {ticker} at {buy_ask} for a total of {transaction_amount} SEK, of which {calculate_brokerage_fee(sell_shares * buy_ask)} SEK fee", 'red'))
                else:
                    print(f'No sell action taken for {ticker} at {datetime_str}. Buy ask price {buy_ask} is not lower than the lowest price {lowest_price} within the threshold.')
            else:
                print(f'No action taken for {ticker} at {datetime_str}. Either not owned or no shares to sell.')
        else:
            print(f'No matching ticker found for orderbook ID {orderbook_id}.')
    except Exception as e:
        print(f"Error processing realtime data: {e}")
        
#realtime_data_dir = './input/'
realtime_data_dir = '/Users/ake/Documents/probable_spoon_a/input/'

#processed_lines = set()
realtime_data_name = datetime.now().strftime("%Y-%m-%d")
async def watch_for_data_changes():
    processed_lines = set()  # Initialize a set to keep track of processed lines
    while True:
        try:
            async for changes in awatch(realtime_data_dir):
                for change in changes:
                    _, path = change
                    if path.endswith(f'realtime_data_{realtime_data_name}_data.csv'):
                        async with aio_open(path, 'r') as file:
                            async for line in file:
                                line = line.strip()
                                if line not in processed_lines:
                                    processed_lines.add(line)
                                    await process_realtime_data(line, whitelisted_tickers, budget)
        except Exception as e:
            # Handle exceptions here, you can log them or take appropriate action
            print(f"An error occurred: {e}")



async def main():
    """Entry point for the realtime module when called from main.py."""
    await watch_for_data_changes()

if __name__ == "__main__":
    asyncio.run(main())