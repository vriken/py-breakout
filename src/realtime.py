from utility import datetime, timedelta, pd, queue, aio_open, ast, get_historical_data, math, calculate_brokerage_fee, cl, awatch, asyncio


budget = 3000
current_date = datetime.now()
start_date_str = "2022-01-10"
end_date = current_date - timedelta(days=1)
end_date_str = end_date.strftime('%Y-%m-%d')


whitelisted_tickers = {'TRANS.ST': 564938, 'SYSR.ST': 97407, 'SANION.ST': 475457,
                       'CNCJO-B.ST': 5279, 'INDT.ST': 26607, 'INSTAL.ST': 752039,
                       'KDEV.ST': 285632, 'K2A-B.ST': 971402, 'NETI-B.ST': 5440,
                       'NIBE-B.ST': 5325}
whitelisted_tickers_parameters = pd.read_csv('input/best_whitelisted.csv')

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

                # Get historical data for the ticker for the last two years
                historical_data = await get_historical_data(ticker, start_date_str, end_date_str, "1d")

                # Calculate prices x = lower_length days ago and x = upper_length days ago
                price_lower_length_days_ago = historical_data['high'].iloc[-int(upper_length):].min()
                price_upper_length_days_ago = historical_data['high'].iloc[-int(upper_length):].max()

                # Adjust the buy signal to include the brokerage fee
                buy_signal = float(buy_price) > price_upper_length_days_ago

                # Adjust the sell signal to include the brokerage fee
                sell_signal = float(buy_price) < price_lower_length_days_ago

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
                            print(f"The price of {ticker}, orderbook id: {orderbook_id} is {buy_price} today.\nThe highest price within {upper_length} days was: {cl(price_upper_length_days_ago, 'blue')}")
                            print(cl(f'Therefore we BUY at {current_datetime.strftime("%Y-%m-%d %H:%M:%S")}: {max_affordable_shares} Shares of {ticker} bought at {(current_price * max_affordable_shares) + fee} SEK, of which {fee} SEK fee', 'green'))
                        else:
                            #print(f"No shares of {ticker} to sell")
                            pass
                    else:
                        print(f"Right now, the price of {ticker} is {current_price}, no action needed.\nWe are waiting for price to hit {price_upper_length_days_ago}, or {price_lower_length_days_ago}")
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
                        print(f"The price of {ticker}, orderbook id: {orderbook_id} is {buy_price} today, and {lower_length} days ago it was: {cl(price_lower_length_days_ago), 'orange'}")
                        print(cl(f'Therefore we SELL at {current_datetime.strftime("%Y-%m-%d %H:%M:%S")}: {sell_shares} Shares of {ticker} sold at ${sell_price}, Profit: ${profit - fee}, of which {fee} SEK fee', 'green'))

                        # Reset the stock entry after selling
                        owned_stocks[ticker]['shares'] = 0
                        owned_stocks[ticker]['buy_price'] = 0
                        budget += total_sell_amount - fee  # Add back the amount after subtracting the fee
                    else:
                        #print(f"No shares of {ticker} to sell")
                        pass
                else:
                    print(f"Right now, the price of {ticker} is {current_price}, no action needed.\nWe are waiting for price to hit {price_upper_length_days_ago}, or {price_lower_length_days_ago}")
                    pass

            # Update the last processed datetime to the current datetime
            last_processed_datetime = current_datetime

    except Exception as e:
        print(f"Error processing real-time data: {e}")

realtime_data_dir = 'input'

processed_lines = set()

async def watch_for_data_changes():
    async for changes in awatch(realtime_data_dir):
        for change in changes:
            _, path = change
            if path.endswith('realtime_data.txt'):
                async with aio_open(path, 'r') as file:
                    async for line in file:
                        if line.strip() not in processed_lines:
                            processed_lines.add(line.strip())
                            await process_realtime_data(line.strip(), whitelisted_tickers, budget) #/len(whitelisted_tickers))



# Continuously monitor real-time data changes
async def main():
    await watch_for_data_changes()

asyncio.run(main())
