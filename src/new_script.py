from utility import donchian, asyncio, get_historical_data, get_historical_data_sync, datetime, timedelta, pd, os, time, calculate_brokerage_fee, log_transaction


async def fetch_historical_data(ticker, values):
    stock = await get_historical_data(ticker, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d'), "1m")
    stock = stock.dropna()
    stock = stock[['date', 'high', 'low', 'ticker']]
    stock['id'] = values['id']
    stock[['dcl', 'dcm', 'dcu']] = stock.ta.donchian(lower_length=values['lower_length'], upper_length=values['upper_length'])
    print(stock)
    return stock

async def load_historical_data():
    # Load csv file
    selected_tickers = pd.read_csv('/Users/ake/Documents/probable_spoon/input/best_tickers.csv')
    # Convert the 'ticker', 'id', 'lower_length', and 'upper_length' columns to a dictionary
    tickers_dict = selected_tickers.set_index('ticker')[['id', 'lower_length', 'upper_length']].to_dict('index')

    # Fetch historical data asynchronously for all tickers
    tasks = [fetch_historical_data(ticker, values) for ticker, values in tickers_dict.items()]
    all_stocks_data = await asyncio.gather(*tasks)

    # Combine all data into a single DataFrame and retain only the latest Donchian channel values
    all_stocks = pd.concat(all_stocks_data).drop_duplicates(subset=['id'], keep='last')
    return all_stocks

def implement_strategy(stock, investment):
    actions = []
    in_position = {}  # Dictionary to track position for each stock
    equity = investment  # Initial investment

    for i in range(3, len(stock)):
        current_date_or_datetime = stock['date'].iloc[i].strftime('%Y-%m-%d %H:%M:%S')
        ticker = stock['ticker'].iloc[i]
        id_ = stock['id'].iloc[i]

        # Initialize in_position for the ticker if it's not already there
        if ticker not in in_position:
            in_position[ticker] = False

        # Buy Condition
        if stock['buy_price'].iloc[i] >= stock['dcu'].iloc[i] and not in_position[ticker]:
            no_of_shares = equity // stock['buy_price'].iloc[i]
            transaction_amount = no_of_shares * stock['buy_price'].iloc[i]
            fee = calculate_brokerage_fee(transaction_amount)
            if equity >= transaction_amount + fee:  # Check if enough equity for the transaction and fee
                equity -= (transaction_amount + fee)
                in_position[ticker] = True  # Update position status
                actions.append(f"BUY,{ticker},{id_},{no_of_shares},{stock['buy_price'].iloc[i]},{current_date_or_datetime}, Fee: {fee}")

        # Sell Condition
        elif stock['sell_price'].iloc[i] <= stock['dcl'].iloc[i] and in_position[ticker]:
            no_of_shares = equity // stock['sell_price'].iloc[i]
            transaction_amount = no_of_shares * stock['sell_price'].iloc[i]
            fee = calculate_brokerage_fee(transaction_amount)
            equity += (transaction_amount - fee)
            in_position[ticker] = False  # Update position status
            actions.append(f"SELL,{ticker},{id_},{no_of_shares},{stock['sell_price'].iloc[i]},{current_date_or_datetime}, Fee: {fee}")

    return actions


def parse_custom_date(date_str):
    date_str = date_str.strip()  # Remove leading/trailing whitespace
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"time data '{date_str}' does not match any expected format")


last_processed_index = -1

async def process_realtime_data(all_stocks, investment):
    global last_processed_index
    current_date = datetime.now().strftime('%Y-%m-%d')
    realtime_file = f'/Users/ake/Documents/probable_spoon/input/realtime_data_{current_date}_data.csv'
    
    if os.path.exists(realtime_file):
        # Load real-time data
        real_time_data = pd.read_csv(realtime_file, names=['id', 'buy_price', 'sell_price', 'date'])
        real_time_data['date'] = real_time_data['date'].apply(parse_custom_date)

        # Process only new data
        new_data = real_time_data.iloc[last_processed_index + 1:]
        if not new_data.empty:
            new_data_merged = new_data.merge(all_stocks[['id', 'ticker', 'dcl', 'dcm', 'dcu']], on='id', how='left')
            actions = implement_strategy(new_data_merged, investment)

            # Print headers and actions if there are new actions
            if actions:
                print("Action,Ticker,ID,Shares,Price,Date")
                for action_str in actions:
                    action_parts = action_str.split(',')
                    if len(action_parts) >= 6:  # Ensure there are enough parts in the action string
                        transaction_type = action_parts[0]
                        ticker = action_parts[1]
                        orderbook_id = action_parts[2]
                        shares = action_parts[3]
                        price = action_parts[4]
                        transaction_date = action_parts[5]
                        
                        # Extract profit if available
                        profit = None
                        if len(action_parts) >= 7:
                            profit = action_parts[6].split(': ')[1]  # Extract the profit part
                            
                        await log_transaction(transaction_type, ticker, orderbook_id, shares, price, transaction_date, profit, file_path='output/model_2_trades.csv')
                        print(action_str)

            # Update the last processed index
            last_processed_index = real_time_data.index[-1]
    else:
        print(f"No real-time data file found for {current_date}")


async def main():
    investment_amount = 1000  # Example investment amount
    all_stocks = await load_historical_data()
    
    # Continuously process real-time data
    while True:
        await process_realtime_data(all_stocks, investment_amount/len(all_stocks))
        #await asyncio.sleep(1)  # You might still want a small delay to avoid constant file access

# Run the main function
asyncio.run(main())