from utility import datetime, timedelta, pd, queue, aio_open, ast, get_data, math, calculate_brokerage_fee, cl, awatch, asyncio

owned_stocks = {}

budget = 1045
# Modify function to accept owned_stocks dictionary
def update_budget_from_past_trades(budget, owned_stocks):
    try:
        trades_df = pd.read_csv('./output/trades.csv')
        for index, row in trades_df.iterrows():
            transaction_amount = row['Shares'] * row['Price']
            ticker = row['Ticker']
            
            if row['Transaction Type'] == 'BUY':
                budget -= transaction_amount
                
                # Update owned_stocks for BUY transaction
                if ticker not in owned_stocks:
                    owned_stocks[ticker] = {'shares': row['Shares'], 'buy_price': row['Price']}
                else:
                    owned_shares = owned_stocks[ticker]['shares']
                    average_price = (owned_shares * owned_stocks[ticker]['buy_price'] + transaction_amount) / (owned_shares + row['Shares'])
                    owned_stocks[ticker]['shares'] += row['Shares']
                    owned_stocks[ticker]['buy_price'] = average_price

            elif row['Transaction Type'] == 'SELL':
                budget += transaction_amount
                
                # Update owned_stocks for SELL transaction
                if ticker in owned_stocks:
                    owned_stocks[ticker]['shares'] -= row['Shares']
                    if owned_stocks[ticker]['shares'] <= 0:
                        del owned_stocks[ticker]
                    
    except FileNotFoundError:
        print("No previous trades file found. Starting with initial budget.")
    
    return budget

# Update budget based on past trades
budget = update_budget_from_past_trades(budget, owned_stocks)

print(owned_stocks)

current_date = datetime.now()
start_date = current_date - timedelta(weeks = 10)
start_date_str = start_date.strftime('%Y-%m-%d')
end_date = current_date - timedelta(days=0)
end_date_str = end_date.strftime('%Y-%m-%d')

# Load the CSV file
selected_stocks_df = pd.read_csv('./input/best_tickers.csv')
# Convert the 'ticker' and 'id' columns to a dictionary
whitelisted_tickers = dict(zip(selected_stocks_df['ticker'], selected_stocks_df['id']))

# Extracting parameters for each ticker
whitelisted_tickers_parameters = {}
for index, row in selected_stocks_df.iterrows():
    ticker = row['ticker']
    params = {
        'lower_length': row['lower_length'],
        'upper_length': row['upper_length']
    }
    whitelisted_tickers_parameters[ticker] = params

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
    if 8 <= transaction_datetime.hour < 17:
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
        current_datetime = parse_datetime(datetime_str)

        # Check if this datetime is newer than the last processed datetime
        if last_processed_datetime is None or current_datetime > last_processed_datetime:
            # Look up the ticker based on the orderbook ID
            ticker = next((key for key, value in tickers.items() if value == int(orderbook_id)), None)

            if ticker:
                # Get the Donchian channel parameters for this ticker
                if ticker in whitelisted_tickers_parameters:
                    params = whitelisted_tickers_parameters[ticker]
                    lower_length = params['lower_length']
                    upper_length = params['upper_length']

                # Get historical data for the ticker for the last two years
                historical_data = get_data(ticker, start_date_str, end_date_str, "1d")

                # Calculate the date limits for lower_length and upper_length
                max_date = historical_data.index.max()
                min_date_lower = max_date - pd.Timedelta(days=lower_length)
                min_date_upper = max_date - pd.Timedelta(days=upper_length)

                # Filter the historical data for the required date ranges
                filtered_data_lower = historical_data[(historical_data.index <= max_date) & (historical_data.index >= min_date_lower)]
                filtered_data_upper = historical_data[(historical_data.index <= max_date) & (historical_data.index >= min_date_upper)]

                # Calculate lowest_price and highest_price
                lowest_price = min(filtered_data_lower['low']) #, float(buy_price))
                highest_price = max(filtered_data_upper['high']) #, float(buy_price))

                # Buy signal: True if current buy_price is higher than the max 'high' price in the last lower_length days
                buy_signal = float(buy_price) > highest_price
                # Sell signal: True if current buy_price is lower than the min 'low' price in the last upper_length days
                sell_signal = float(buy_price) < lowest_price

                # Print the current price and buy/sell decision
                current_price = float(buy_price)  # Assuming you want to use the buy price for the current price

                if buy_signal:
                    if ticker not in owned_stocks or owned_stocks[ticker]['shares'] == 0:
                        # Calculate the maximum number of shares that can be bought within the budget
                        max_budget_for_stock = min(budget * 0.2, budget)
                        max_affordable_shares = math.floor(max_budget_for_stock / (current_price * 1.0025))  # Including brokerage fee
                        if max_affordable_shares > 0:
                            transaction_amount = max_affordable_shares * current_price
                            fee = calculate_brokerage_fee(transaction_amount)
                            
                            if transaction_amount + fee <= max_budget_for_stock:

                                owned_stocks[ticker] = {'shares': max_affordable_shares, 'buy_price': current_price}
                                budget -= transaction_amount + fee  # Include brokerage fee
                                
                                await log_transaction('BUY', ticker, orderbook_id, max_affordable_shares, current_price, current_datetime.strftime('%Y-%m-%d %H:%M:%S'))
                                print(f"The price of {ticker}, orderbook id: {orderbook_id} is {buy_price} today.\nThe highest price within {upper_length} days was: {highest_price}")
                                print(cl(f'Therefore we BUY at {current_datetime.strftime("%Y-%m-%d %H:%M:%S")}: {max_affordable_shares} Shares of {ticker} bought at {(current_price * max_affordable_shares) + fee} SEK, of which {fee} SEK fee', 'green'))
                            else:
                                print(f'Not enough budget to buy {ticker}. Required:  {transaction_amount + fee} SEK, Available: {max_budget_for_stock} SEK')
                        else:
                            #print(f"No shares of {ticker} to sell")
                            pass
                    else:
                        print(f"Right now, the price of {ticker} is {current_price}, no action needed.\nWe are waiting for price to hit {highest_price}, or {lowest_price}")
                        pass

                elif sell_signal:
                    if ticker in owned_stocks and owned_stocks[ticker]['shares'] > 0:
                        sell_shares = owned_stocks[ticker]['shares']
                        sell_price = current_price
                        total_sell_amount = sell_shares * sell_price
                        fee = calculate_brokerage_fee(total_sell_amount)

                        total_buy_amount = sell_shares * owned_stocks[ticker]['buy_price']
                        profit = total_sell_amount - total_buy_amount - fee  # Subtract brokerage fee from profit

                        await log_transaction('SELL', ticker, orderbook_id, sell_shares, sell_price, current_datetime.strftime('%Y-%m-%d %H:%M:%S'), profit)
                        print(f"The price of {ticker}, orderbook id: {orderbook_id} is {buy_price} today, and {lower_length} days ago it was: {lowest_price}")
                        print(cl(f'Therefore we SELL at {current_datetime.strftime("%Y-%m-%d %H:%M:%S")}: {sell_shares} Shares of {ticker} sold at ${sell_price}, Profit: ${profit - fee}, of which {fee} SEK fee', 'green'))

                        # Reset the stock entry after selling
                        owned_stocks[ticker]['shares'] = 0
                        owned_stocks[ticker]['buy_price'] = 0
                        budget += total_sell_amount - fee  # Add back the amount after subtracting the fee
                    else:
                        #print(f"No shares of {ticker} to sell")
                        pass
                else:
                    print(f"Right now, the price of {ticker} is {current_price}, no action needed.\nWe are waiting for price to hit {highest_price}, or {lowest_price}")
                    pass

            # Update the last processed datetime to the current datetime
            last_processed_datetime = current_datetime

    except Exception as e:
        print(f"Error processing real-time data: {e}")

realtime_data_dir = './input/'

processed_lines = set()

realtime_data_name = datetime.now().strftime("%Y-%m-%d")

async def watch_for_data_changes():
    async for changes in awatch(realtime_data_dir):
        for change in changes:
            _, path = change
            if path.endswith(f'{realtime_data_name}_data.csv'):
                async with aio_open(path, 'r') as file:
                    async for line in file:
                        if line.strip() not in processed_lines:
                            processed_lines.add(line.strip())
                            await process_realtime_data(line.strip(), whitelisted_tickers, budget)



# Continuously monitor real-time data changes
async def main():
    await watch_for_data_changes()

asyncio.run(main())
