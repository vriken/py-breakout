from utility import pd, datetime, timedelta, get_historical_data_sync, implement_strategy, BayesianOptimization
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load ticker data from a CSV file
ticker_df = pd.read_csv('/Users/ake/Documents/probable_spoon/input/best_tickers.csv')
ticker_list = ticker_df['ticker'].tolist()


# Define the parameter space
pbounds = {
    'lower_length': (1, 5),
    'upper_length': (5, 15)
}

def objective_for_ticker(ticker, lower_length, upper_length):
    try:
        print(f"Processing {ticker}")
        current_date = datetime.now()
        start_date = current_date - timedelta(weeks = 52*2)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date = current_date - timedelta(days=1)
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        stock = get_historical_data_sync(ticker, start_date_str, end_date_str, "1wk")
        stock.index.name = 'date'
        stock[['dcl', 'dcm', 'dcu']] = stock.ta.donchian(lower_length=lower_length, upper_length=upper_length)
        stock = stock.dropna()
        stock.index = pd.to_datetime(stock.index)
        
        _, _, earning = implement_strategy(stock, 1000, lower_length, upper_length)
        return earning

    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return 0

def optimize_for_ticker(ticker):
    try:
        optimizer = BayesianOptimization(
            f=lambda lower_length, upper_length: objective_for_ticker(ticker, lower_length, upper_length),
            pbounds=pbounds,
            random_state=1,
            allow_duplicate_points=True
        )

        optimizer.maximize(init_points=5, n_iter=20)
        return optimizer.max

    except Exception as e:
        print(f"Error optimizing {ticker}: {e}")
        return None
72
results = []

# Process each ticker in parallel and collect results
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(optimize_for_ticker, ticker): ticker for ticker in ticker_list}
    for future in as_completed(futures):
        params = future.result()
        if params is not None:
            ticker = futures[future]
            results.append([ticker, params['target'], params['params']['lower_length'], params['params']['upper_length']])

# Save results to a CSV file
result_df = pd.DataFrame(results, columns=['ticker', 'target', 'lower_length', 'upper_length'])
result_df.to_csv('/Users/ake/Documents/probable_spoon/input/best_tickers_without_id.csv', index=False)
