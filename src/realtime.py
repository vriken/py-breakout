from utility import get_balance, get_owned_stocks, read_csv, parse_datetime, get_data, datetime, timedelta, floor, calculate_brokerage_fee, log_transaction, cl, awatch, aio_open, randint
import asyncio

budget = get_balance()
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
#start_date_str = (current_date - timedelta(days = 80)).strftime('%Y-%m-%d')
start_date_str = (current_date - timedelta(days = max(int(donchian_parameters[ticker]['upper_length'])))).strftime('%Y-%m-%d')
end_date_str = (current_date - timedelta(days = 1)).strftime('%Y-%m-%d')

historical_data_dict = {}
# This takes like a minute, figure out a way to store this more effectively
print('fetching historical data')
for ticker, ticker_id in whitelisted_tickers.items():
    if ticker:
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
print('done fetching historical data')
        
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
# Displaying the results
#for ticker in tickers.keys():
#    print(f"{ticker} - Highest price in last {donchian_parameters[ticker]['upper_length']} days: {highest_prices.get(ticker, 'N/A')}")
#    print(f"{ticker} - Lowest price in last {donchian_parameters[ticker]['lower_length']} days: {lowest_prices.get(ticker, 'N/A')}\n")


async def process_realtime_data(data, ticker, budget):
    try:
        orderbook_id, buy_ask, sell_ask, datetime_str = data.split(',')
        ticker = next((key for key, value in ticker.items() if value == int(orderbook_id)), None)
        
        if ticker:
            # Rounding to 3 so that we can get the buy order in before the price actually hits.
            highest_price = round(highest_prices.get(ticker), 3)
            lowest_price = round(lowest_prices.get(ticker), 3)
            
            buy_ask = float(buy_ask)
            sell_ask = float(sell_ask)
            # Buy logic
            if orderbook_id not in owned_stocks or owned_stocks[orderbook_id]['shares'] == 0:
                max_budget_for_stock = min(budget * 0.2, budget)
                max_affordable_shares = floor(max_budget_for_stock / (sell_ask + calculate_brokerage_fee(sell_ask)))
                
                if max_affordable_shares > 0:
                    shares_to_buy = randint(1, max_affordable_shares)
                    
                    if sell_ask > highest_price:
                        transaction_amount = shares_to_buy * sell_ask + calculate_brokerage_fee(shares_to_buy * sell_ask)
                        budget = budget - transaction_amount
                        
                        #print('error is here')
                        owned_stocks[orderbook_id] = {
                            'name'      : ticker,
                            'price'     : sell_ask,
                            'shares'    : shares_to_buy,
                            'id'        : orderbook_id
                        }
                        
                        await log_transaction('BUY', ticker, orderbook_id, shares_to_buy, sell_ask, current_date.strftime('%Y-%m-%d %H:%M:%S'))
                        print(f"At {datetime_str}, {ticker} with id {orderbook_id} is {sell_ask}. The highest price within {upper_length} days was {highest_price}")
                        print(cl(f"Test At {datetime_str}, we BUY {shares_to_buy} shares of {ticker} at {sell_ask} for a total of {transaction_amount} SEK, of which {calculate_brokerage_fee(shares_to_buy * sell_ask)} SEK fee", 'green'))
                    else:
                        print(f'At {datetime_str}, {ticker} is {sell_ask}, we buy at {highest_price}')
                else:
                    #print(f'no budget for {ticker}')
                    pass
                    #print(f'At {datetime_str}, budget is {budget}, {ticker} costs {sell_ask}')
                    
            # Sell logic
            elif orderbook_id in owned_stocks and owned_stocks[orderbook_id]['shares'] > 0:
                if(buy_ask < lowest_price):
                    sell_shares = owned_stocks[orderbook_id]['shares']
                    sell_price = buy_ask
                    
                    transaction_amount = sell_shares * sell_price
                    budget = budget + transaction_amount - calculate_brokerage_fee(sell_shares * sell_price)
                    
                    await log_transaction('SELL', ticker, orderbook_id, sell_shares, sell_price, current_date.strftime('%Y-%m-%d %H:%M:%S'))
                    print(f"At {datetime_str}, {ticker} with id {orderbook_id} is {buy_ask}. The lowest price within {lower_length} days was {lowest_price}, therefore")
                    print(cl(f"At {datetime_str}, we SELL {sell_shares} shares of {ticker} at {buy_ask} for a total of {transaction_amount} SEK, of which {calculate_brokerage_fee(sell_shares * buy_ask)} SEK fee", 'red'))
                    owned_stocks[orderbook_id]['shares'] = 0
                else:
                    print(f'At {datetime_str}, {ticker} is {buy_ask}, we sell at {lowest_price}')
            else:
                pass
        else:
            pass
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

# Run the function in an asyncio event loop
if __name__ == "__main__":
    asyncio.run(watch_for_data_changes())

#asyncio.run(main())